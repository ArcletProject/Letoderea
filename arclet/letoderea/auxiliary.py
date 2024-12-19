import asyncio
from abc import ABCMeta, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Final, Generic, Literal, Optional, TypeVar, Union, overload

from tarina import run_always_await

from .exceptions import JudgementError, ParsingStop, PropagationCancelled, UndefinedRequirement, UnexpectedArgument
from .provider import Param, Provider, ProviderFactory
from .typing import Contexts, Force

T = TypeVar("T")
Q = TypeVar("Q")
D = TypeVar("D")


class Interface(Generic[T]):
    def __init__(self, ctx: Contexts, providers: list[Union[Provider, ProviderFactory]]):
        self.ctx = ctx
        self.providers = providers
        self.cache: dict[tuple, Any] = {}
        self.executed: set[str] = set()

    @staticmethod
    def stop():
        raise ParsingStop

    @staticmethod
    def block():
        raise PropagationCancelled

    def clear(self):
        self.ctx.clear()

    class Update(dict):
        pass

    @classmethod
    def update(cls, **kwargs):
        return cls.Update(kwargs)

    @property
    def event(self) -> T:
        return self.ctx["$event"]

    @property
    def result(self) -> T:
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


class Scope(str, Enum):
    prepare = "prepare"
    complete = "complete"
    cleanup = "cleanup"


@dataclass(init=False, eq=True, unsafe_hash=True)
class BaseAuxiliary(metaclass=ABCMeta):

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
    def scopes(self) -> set[Scope]:
        raise NotImplementedError

    @property
    @abstractmethod
    def id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def __call__(self, scope: Scope, interface: Interface)-> Optional[Union[Interface.Update, bool]]:
        raise NotImplementedError


def auxilia(
    name: str,
    prepare: Optional[Callable[[Interface], Optional[Union[Interface.Update, bool]]]] = None,
    complete: Optional[Callable[[Interface], Optional[Interface]]] = None,
    cleanup: Optional[Callable[[Interface], Optional[Union[Interface.Update, bool]]]] = None,
    before: Optional[set[str]] = None,
    after: Optional[set[str]] = None,
):
    class _Auxiliary(BaseAuxiliary):
        async def __call__(self, scope: Scope, interface: Interface):
            res = None
            if scope == Scope.prepare and prepare is not None:
                res = await run_always_await(prepare, interface)
            if scope == Scope.complete and complete is not None:
                res = await run_always_await(complete, interface)
            if scope == Scope.cleanup and cleanup is not None:
                res = await run_always_await(cleanup, interface)
            return res

        @property
        def scopes(self) -> set[Scope]:
            return {Prepare, Complete, Cleanup}

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


Prepare: Final = Scope.prepare
Complete: Final = Scope.complete
Cleanup: Final = Scope.cleanup


async def prepare(aux: list[BaseAuxiliary], interface: Interface):
    for _aux in aux:
        res = await _aux(Prepare, interface)
        if res is None:
            continue
        if res is False:
            raise JudgementError
        interface.executed.add(_aux.id)
        if isinstance(res, interface.Update):
            interface.ctx.update(res)


async def complete(aux: list[BaseAuxiliary], interface: Interface):
    keys = set(interface.ctx.keys())
    for _aux in aux:
        res = await _aux(Complete, interface)
        if res is None:
            continue
        if res is False:
            raise JudgementError
        interface.executed.add(_aux.id)
        if isinstance(res, interface.Update):
            if keys.issuperset(res.keys()):
                interface.ctx.update(res)
                continue
            raise UnexpectedArgument(f"Unexpected argument in {keys - set(res.keys())}")


async def cleanup(aux: list[BaseAuxiliary], interface: Interface):
    res = await asyncio.gather(*[_aux(Cleanup, interface) for _aux in aux], return_exceptions=True)
    if False in res:
        raise JudgementError
    for _res in res:
        if isinstance(_res, Exception):
            raise _res


def sort_auxiliaries(auxiliaries: list[BaseAuxiliary]) -> list[BaseAuxiliary]:
    auxs = {aux.id: aux for aux in auxiliaries}
    if len(auxs) < 2:
        return [auxs.popitem()[1]]

    # 构造图和入度表
    graph = defaultdict(set)  # 邻接表
    in_degree = defaultdict(int)  # 入度表

    # 初始化所有节点的入度
    for node in auxs:
        in_degree[node] = 0  # 初始入度为 0

    # 构造图和更新入度表
    for aux in auxs.values():
        current = aux.id
        # 处理 "before" 依赖
        for before in aux.before:
            graph[before].add(current)  # before -> current
            in_degree[current] += 1  # current 入度 +1
        # 处理 "after" 依赖
        for after in aux.after:
            graph[current].add(after)  # current -> after
            in_degree[after] += 1  # after 入度 +1

    # 拓扑排序
    result = []
    queue = deque([node for node in auxs if in_degree[node] == 0])  # 入度为 0 的节点入队

    while queue:
        node = queue.popleft()  # 取出队首节点
        result.append(node)

        # 遍历该节点的邻居
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1  # 邻居入度 -1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)  # 邻居入度为 0，加入队列

    # 检查是否有循环依赖
    if len(result) < len(auxs):
        raise ValueError("存在循环依赖，无法进行拓扑排序")

    return [auxs[aux_id] for aux_id in result]
