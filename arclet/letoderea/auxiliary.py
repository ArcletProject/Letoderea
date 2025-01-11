import inspect
from abc import ABCMeta, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Generic, Literal, NamedTuple, Optional, TypeVar, Union, overload

from tarina import run_always_await

from .exceptions import JudgementError, ParsingStop, PropagationCancelled, UndefinedRequirement, UnexpectedArgument
from .provider import Param, Provider, ProviderFactory
from .typing import Contexts, Force, TTarget
from .event import EVENT

T = TypeVar("T")
Q = TypeVar("Q")
D = TypeVar("D")


class Interface(Generic[T]):
    def __init__(self, ctx: Contexts, providers: list[Union[Provider, ProviderFactory]]):
        self.ctx: Contexts = ctx
        self.providers = providers
        self.cache: dict[tuple, Any] = {}
        self.executed: dict[str, "BaseAuxiliary"] = {}

    @staticmethod
    def stop():
        raise ParsingStop

    @staticmethod
    def block():
        raise PropagationCancelled

    def clear(self):
        self.ctx = {}  # type: ignore
        self.cache.clear()
        self.executed.clear()

    class Update(dict):
        pass

    @classmethod
    def update(cls, **kwargs):
        return cls.Update(kwargs)

    @property
    def event(self) -> T:
        return self.ctx[EVENT]  # type: ignore

    @property
    def result(self) -> Any:
        return self.ctx["$result"]

    @property
    def error(self) -> Optional[Exception]:
        return self.ctx.get("$error")

    @overload
    async def query(self, typ: type[Q], name: str) -> Q: ...

    @overload
    async def query(self, typ: type[Q], name: str, *, force_return: Literal[True]) -> Optional[Q]: ...

    @overload
    async def query(self, typ: type[Q], name: str, default: D) -> Union[Q, D]: ...

    async def query(self, typ: type, name: str, default: Any = None, force_return: bool = False):
        if name in self.ctx:
            return self.ctx[name]
        providers = []
        param = Param(name, typ, default, False)
        if param in self.cache:
            return self.cache[param]
        for _provider in self.providers:
            if isinstance(_provider, ProviderFactory):
                if result := _provider.validate(param):
                    providers.append(result)
            elif _provider.validate(param):
                providers.append(_provider)
        for provider in providers:
            res = await provider(self.ctx)
            if res is None:
                continue
            if res.__class__ is Force:
                res = res.value
            self.cache[param] = res
            return res
        if force_return:
            self.cache[param] = default
            return default
        raise UndefinedRequirement(name, typ, default, self.providers)


@dataclass(init=False, eq=True, unsafe_hash=True)
class BaseAuxiliary(metaclass=ABCMeta):
    _overrides: ClassVar[dict[str, bool]] = {}

    @property
    def before(self) -> set[str]:
        """Auxiliaries that should run before to this one"""
        return set()

    @property
    def after(self) -> set[str]:
        """Auxiliaries that should run after to this one"""
        return set()

    @property
    @abstractmethod
    def id(self) -> str:
        raise NotImplementedError

    async def on_prepare(self, interface: Interface) -> Optional[Union[Interface.Update, bool]]:
        return

    async def on_complete(self, interface: Interface) -> Optional[Union[Interface.Update, bool]]:
        return

    async def on_cleanup(self, interface: Interface) -> Optional[bool]:
        return

    def __init_subclass__(cls, **kwargs):
        cls._overrides = {
            "prepare": cls.on_prepare != BaseAuxiliary.on_prepare,
            "complete": cls.on_complete != BaseAuxiliary.on_complete,
            "cleanup": cls.on_cleanup != BaseAuxiliary.on_cleanup,
        }

    def __call__(self, target: TTarget) -> TTarget:
        if not hasattr(target, "__auxiliaries__"):
            setattr(target, "__auxiliaries__", [self])
        else:
            getattr(target, "__auxiliaries__").append(self)
        return target

    bind = __call__


def auxilia(
    name: str,
    prepare: Optional[Callable[[Interface], Optional[Union[Interface.Update, bool]]]] = None,
    complete: Optional[Callable[[Interface], Optional[Union[Interface.Update, bool]]]] = None,
    cleanup: Optional[Callable[[Interface], Optional[bool]]] = None,
    before: Optional[set[str]] = None,
    after: Optional[set[str]] = None,
):
    class _Auxiliary(BaseAuxiliary):
        if prepare is not None:

            async def on_prepare(self, interface: Interface) -> Optional[Union[Interface.Update, bool]]:
                if TYPE_CHECKING:
                    assert prepare
                return await run_always_await(prepare, interface)

        if complete is not None:

            async def on_complete(self, interface: Interface) -> Optional[Interface.Update]:
                if TYPE_CHECKING:
                    assert complete
                return await run_always_await(complete, interface)

        if cleanup is not None:

            async def on_cleanup(self, interface: Interface) -> Optional[bool]:
                if TYPE_CHECKING:
                    assert cleanup
                return await run_always_await(cleanup, interface)

        @property
        def id(self) -> str:
            return name

        @property
        def before(self) -> set[str]:
            return before or set()

        @property
        def after(self) -> set[str]:
            return after or set()

    return _Auxiliary()


async def prepare(aux: list[BaseAuxiliary], interface: Interface):
    for _aux in aux:
        res = await _aux.on_prepare(interface)
        if res is None:
            continue
        if res is False:
            raise JudgementError
        interface.executed[_aux.id] = _aux
        if isinstance(res, interface.Update):
            interface.ctx.update(res)


async def complete(aux: list[BaseAuxiliary], interface: Interface):
    keys = set(interface.ctx.keys())
    for _aux in aux:
        res = await _aux.on_complete(interface)
        if res is None:
            continue
        if res is False:
            raise JudgementError
        interface.executed[_aux.id] = _aux
        if isinstance(res, interface.Update):
            if keys.issuperset(res.keys()):
                interface.ctx.update(res)
                continue
            raise UnexpectedArgument(f"Unexpected argument in {keys - set(res.keys())}")


async def cleanup(aux: list[BaseAuxiliary], interface: Interface):
    for _aux in aux:
        res = await _aux.on_cleanup(interface)
        if res is False:
            raise JudgementError
        interface.executed[_aux.id] = _aux


class _Auxiliary(NamedTuple):
    id: str
    before: set[str]
    after: set[str]
    group: list[BaseAuxiliary]


def sort_auxiliaries(auxiliaries: list[BaseAuxiliary]) -> list[BaseAuxiliary]:
    auxs: dict[str, _Auxiliary] = {}
    for aux in auxiliaries:
        if aux.id not in auxs:
            auxs[aux.id] = _Auxiliary(aux.id, aux.before, aux.after, [aux])
        else:
            auxs[aux.id].group.append(aux)
    # construct graph and in-degree table
    graph = defaultdict(set)
    in_degree = defaultdict(int)
    for node in auxs:
        in_degree[node] = 0

    for aux in auxs.values():
        for before in aux.before:
            if before not in auxs:
                continue
            graph[before].add(aux.id)
            in_degree[aux.id] += 1
        for after in aux.after:
            if after not in auxs:
                continue
            graph[aux.id].add(after)
            in_degree[after] += 1

    result = []
    queue = deque([node for node in in_degree if in_degree[node] == 0])

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(auxs):
        raise ValueError("Cycle detected in auxiliaries")

    return [aux for node in result for aux in auxs[node].group]


@lru_cache(4096)
def get_auxiliaries(event: Any) -> list[BaseAuxiliary]:
    res = []
    for cls in reversed(event.__mro__[:-1]):  # type: ignore
        res.extend(getattr(cls, "auxiliaries", []))
    res.extend(
        p
        for _, p in inspect.getmembers(
            event,
            lambda x: inspect.isclass(x) and issubclass(x, BaseAuxiliary),
        )
    )
    auxiliaries: list[BaseAuxiliary] = [a() if isinstance(a, type) else a for a in res]
    return list({a.id: a for a in auxiliaries}.values())


global_auxiliaries: list[BaseAuxiliary] = []
