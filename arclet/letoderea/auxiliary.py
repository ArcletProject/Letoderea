from __future__ import annotations

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum
from functools import partial
from typing import Any, Awaitable, Callable, Literal, Optional, Protocol, overload, Final
from tarina import run_always_await
from .typing import Contexts


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

    @property
    @abstractmethod
    def scopes(self) -> set[Scope]:
        raise NotImplementedError

    def __init__(self, atype: AuxType, mode: CombineMode = CombineMode.SINGLE):
        self.type = atype
        self.mode = mode

    @abstractmethod
    async def __call__(self, scope: Scope, context: Contexts):
        raise NotImplementedError


class SupplyAuxiliary(BaseAuxiliary):
    def __init__(self, mode: CombineMode = CombineMode.SINGLE):
        super().__init__(AuxType.supply, mode)

    @abstractmethod
    async def __call__(self, scope: Scope, context: Contexts) -> Optional[Contexts]:
        raise NotImplementedError


class JudgeAuxiliary(BaseAuxiliary):
    def __init__(self, mode: CombineMode = CombineMode.SINGLE):
        super().__init__(AuxType.judge, mode)

    @abstractmethod
    async def __call__(self, scope: Scope, context: Contexts) -> Optional[bool]:
        raise NotImplementedError


class Executor(Protocol):
    async def __call__(self, scope: Scope, context: Contexts):
        ...


class CombineExecutor:
    steps: list[Callable[[Scope, Contexts], Awaitable]]

    def __init__(self, auxes: list[BaseAuxiliary]):
        self.steps = []
        ors = []

        async def _ors(_scope: Scope, ctx: Contexts, *, funcs: list[BaseAuxiliary]):
            res = None
            for func in funcs:
                res = await func(_scope, ctx)
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

    async def __call__(self, scope: Scope, context: Contexts) -> Optional[bool]:
        res = None
        ctx = context
        last = None
        for step in self.steps:
            if (last := await step(scope, ctx)) is None:
                continue
            if isinstance(last, dict):
                ctx = last
                continue
            if last is False:
                return False
            if res is None:
                res = last
            res &= last
        return ctx if isinstance(last, dict) else res


def combine(auxiliaries: list[BaseAuxiliary]) -> list[Executor]:
    cb = []
    res = []
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
    prepare: Callable[[Contexts], Optional[Contexts]] | None = None,
    complete: Callable[[Contexts], Optional[Contexts]] | None = None,
    cleanup: Callable[[Contexts], Optional[Contexts]] | None = None,
):
    ...


@overload
def auxilia(
    atype: Literal[AuxType.judge],
    mode: CombineMode = CombineMode.SINGLE,
    prepare: Callable[[Contexts], Optional[bool]] | None = None,
    complete: Callable[[Contexts], Optional[bool]] | None = None,
    cleanup: Callable[[Contexts], Optional[bool]] | None = None,
):
    ...


def auxilia(
    atype: AuxType,
    mode: CombineMode = CombineMode.SINGLE,
    prepare: Callable[[Contexts], Any] | None = None,
    complete: Callable[[Contexts], Any] | None = None,
    cleanup: Callable[[Contexts], Any] | None = None,
):
    class _Auxiliary(BaseAuxiliary):
        async def __call__(self, scope: Scope, context: Contexts):
            res = None
            if scope == Scope.prepare and prepare is not None:
                res = await run_always_await(prepare, context)
            if scope == Scope.complete and complete is not None:
                res = await run_always_await(complete, context)
            if scope == Scope.cleanup and cleanup is not None:
                res = await run_always_await(cleanup, context)
            return res if res is False else context

        @property
        def scopes(self) -> set[Scope]:
            return {Prepare, Complete, Cleanup}

    return _Auxiliary(atype, mode)


And: Final = CombineMode.AND
Or: Final = CombineMode.OR
Single: Final = CombineMode.SINGLE
Prepare: Final = Scope.prepare
Parsing: Final = Scope.parsing
Complete: Final = Scope.complete
Cleanup: Final = Scope.cleanup
