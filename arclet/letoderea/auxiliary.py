import asyncio
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, ClassVar, Final, Generic, Literal, Optional, TypeVar, Union, overload

from tarina import run_always_await

from .exceptions import JudgementError, ParsingStop, PropagationCancelled, UndefinedRequirement, UnexpectedArgument
from .provider import Param, Provider, ProviderFactory
from .typing import Contexts

T = TypeVar("T")
Q = TypeVar("Q")
D = TypeVar("D")


class Interface(Generic[T]):
    def __init__(self, ctx: Contexts, providers: list[Union[Provider, ProviderFactory]]):
        self.ctx = ctx
        self.providers = providers
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
    def query(self, typ: type[Q], name: str) -> Q: ...

    @overload
    def query(self, typ: type[Q], name: str, *, force_return: Literal[True]) -> Optional[Q]: ...

    @overload
    def query(self, typ: type[Q], name: str, default: D) -> Union[Q, D]: ...

    def query(self, typ: type, name: str, default: Any = None, force_return: bool = False):
        if name in self.ctx:
            return self.ctx[name]
        for _provider in self.providers:
            if isinstance(_provider, ProviderFactory):
                if result := _provider.validate(Param(name, typ, default, False)):
                    return result(self.ctx)
            elif _provider.validate(Param(name, typ, default, False)):
                return _provider(self.ctx)
        if force_return:
            return default
        raise UndefinedRequirement(name, typ, default, self.providers)


class AuxType(str, Enum):
    supply = "supply"
    judge = "judge"


class Scope(str, Enum):
    prepare = "prepare"
    complete = "complete"
    cleanup = "cleanup"


@dataclass(init=False, eq=True, unsafe_hash=True)
class BaseAuxiliary(metaclass=ABCMeta):
    type: AuxType
    priority: ClassVar[int] = 20

    @property
    @abstractmethod
    def scopes(self) -> set[Scope]:
        raise NotImplementedError

    @property
    @abstractmethod
    def id(self) -> str:
        raise NotImplementedError

    def __init__(self, atype: AuxType, priority: int = 20):
        self.type = atype
        self.__class__.priority = priority

    @abstractmethod
    async def __call__(self, scope: Scope, interface: Interface):
        raise NotImplementedError


class SupplyAuxiliary(BaseAuxiliary):
    def __init__(self, priority: int = 20):
        super().__init__(AuxType.supply, priority)

    @abstractmethod
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[Interface.Update]:
        raise NotImplementedError


class JudgeAuxiliary(BaseAuxiliary):
    def __init__(self, priority: int = 20):
        super().__init__(AuxType.judge, priority)

    @abstractmethod
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        raise NotImplementedError


@overload
def auxilia(
    name: str,
    atype: Literal[AuxType.supply],
    priority: int = 20,
    prepare: Optional[Callable[[Interface], Optional[Interface.Update]]] = None,
    complete: Optional[Callable[[Interface], Optional[Interface.Update]]] = None,
): ...


@overload
def auxilia(
    name: str,
    atype: Literal[AuxType.judge],
    priority: int = 20,
    prepare: Optional[Callable[[Interface], Optional[bool]]] = None,
    complete: Optional[Callable[[Interface], Optional[bool]]] = None,
    cleanup: Optional[Callable[[Interface], Optional[bool]]] = None,
): ...


def auxilia(
    name: str,
    atype: AuxType,
    priority: int = 20,
    prepare: Optional[Callable[[Interface], Any]] = None,
    complete: Optional[Callable[[Interface], Any]] = None,
    cleanup: Optional[Callable[[Interface], Any]] = None,
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

    return _Auxiliary(atype, priority)


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
