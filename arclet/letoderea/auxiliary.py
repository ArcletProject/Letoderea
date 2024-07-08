from __future__ import annotations

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum
from functools import partial
from typing import Any, Awaitable, Callable, ClassVar, Final, Literal, Optional, Protocol, overload, TypeVar, Generic

from tarina import run_always_await

from .provider import Provider, ProviderFactory, Param
from .typing import Contexts

T = TypeVar("T")
Q = TypeVar("Q")
D = TypeVar("D")


class Interface(Generic[T]):
    def __init__(self, ctx: Contexts, providers: list[Provider | ProviderFactory]):
        self.ctx = ctx
        self.providers = providers

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

    @overload
    def query(self, typ: type[Q], name: str) -> Q | None:
        ...

    @overload
    def query(self, typ: type[Q], name: str, default: D) -> Q | D:
        ...

    def query(self, typ: type, name: str, default: Any = None):
        if name in self.ctx:
            return self.ctx[name]
        for _provider in self.providers:
            if isinstance(_provider, ProviderFactory):
                if result := _provider.validate(Param(name, typ, default, False)):
                    return result(self.ctx)
            elif _provider.validate(Param(name, typ, default, False)):
                return _provider(self.ctx)
        return default


class AuxType(str, Enum):
    supply = "supply"
    judge = "judge"
    depend = "depend"


class CombineMode(str, Enum):
    AND = "and"
    OR = "or"
    SINGLE = "single"


class Scope(str, Enum):
    prepare = "prepare"
    parsing = "parsing"
    complete = "complete"
    cleanup = "cleanup"


@dataclass(init=False, eq=True, unsafe_hash=True)
class BaseAuxiliary(metaclass=ABCMeta):
    type: AuxType
    mode: CombineMode
    priority: ClassVar[int] = 20

    @property
    @abstractmethod
    def scopes(self) -> set[Scope]:
        raise NotImplementedError

    def __init__(self, atype: AuxType, mode: CombineMode = CombineMode.SINGLE, priority: int = 20):
        self.type = atype
        self.mode = mode
        self.__class__.priority = priority

    @abstractmethod
    async def __call__(self, scope: Scope, interface: Interface):
        raise NotImplementedError


class SupplyAuxiliary(BaseAuxiliary):
    def __init__(self, mode: CombineMode = CombineMode.SINGLE, priority: int = 20):
        super().__init__(AuxType.supply, mode, priority)

    @abstractmethod
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[Interface.Update]:
        raise NotImplementedError


class JudgeAuxiliary(BaseAuxiliary):
    def __init__(self, mode: CombineMode = CombineMode.SINGLE, priority: int = 20):
        super().__init__(AuxType.judge, mode, priority)

    @abstractmethod
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        raise NotImplementedError


class Executor(Protocol):
    async def __call__(self, scope: Scope, interface: Interface): ...


class CombineExecutor:
    steps: list[Callable[[Scope, Interface], Awaitable]]

    def __init__(self, auxes: list[BaseAuxiliary]):
        self.steps = []
        ors = []

        async def _ors(_scope: Scope, interface: Interface, *, funcs: list[BaseAuxiliary]):
            res = None
            for func in funcs:
                res = await func(_scope, interface)
                if res is None:
                    continue
                if res:
                    return res
            return res

        for aux in auxes:
            if aux.mode == CombineMode.AND:
                if ors:
                    ors.append(aux)
                    self.steps.append(partial(_ors, funcs=ors.copy()))
                    ors.clear()
                else:
                    self.steps.append(aux)
            elif aux.mode == CombineMode.OR:
                ors.append(aux)
        if ors:
            self.steps.append(partial(_ors, funcs=ors.copy()))
            ors.clear()

    async def __call__(self, scope: Scope, interface: Interface):
        res = {}
        for step in self.steps:
            if (last := await step(scope, interface)) is None:
                continue
            if isinstance(last, dict):
                interface.ctx.update(last)
                res.update(last)
            elif last is False:
                return False
            elif last is True:
                continue
        return res or True


def combine(auxiliaries: list[BaseAuxiliary]) -> list[Executor]:
    cb = []
    res = []
    auxiliaries.sort(key=lambda x: x.priority)
    for aux in auxiliaries:
        if aux.mode == CombineMode.SINGLE:
            if cb:
                res.append(CombineExecutor(cb))
                cb.clear()
            res.append(aux)
        else:
            cb.append(aux)
    return res


@overload
def auxilia(
    atype: Literal[AuxType.supply],
    mode: CombineMode = CombineMode.SINGLE,
    priority: int = 20,
    prepare: Callable[[Interface], Optional[Interface.Update]] | None = None,
    complete: Callable[[Interface], Optional[Interface.Update]] | None = None,
    cleanup: Callable[[Interface], Optional[Interface.Update]] | None = None,
): ...


@overload
def auxilia(
    atype: Literal[AuxType.judge],
    mode: CombineMode = CombineMode.SINGLE,
    priority: int = 20,
    prepare: Callable[[Interface], Optional[bool]] | None = None,
    complete: Callable[[Interface], Optional[bool]] | None = None,
    cleanup: Callable[[Interface], Optional[bool]] | None = None,
): ...


def auxilia(
    atype: AuxType,
    mode: CombineMode = CombineMode.SINGLE,
    priority: int = 20,
    prepare: Callable[[Interface], Any] | None = None,
    complete: Callable[[Interface], Any] | None = None,
    cleanup: Callable[[Interface], Any] | None = None,
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

    return _Auxiliary(atype, mode, priority)


And: Final = CombineMode.AND
Or: Final = CombineMode.OR
Single: Final = CombineMode.SINGLE
Prepare: Final = Scope.prepare
Parsing: Final = Scope.parsing
Complete: Final = Scope.complete
Cleanup: Final = Scope.cleanup
