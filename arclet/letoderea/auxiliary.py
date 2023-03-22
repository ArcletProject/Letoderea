from __future__ import annotations

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from functools import partial
from typing import Optional, Awaitable, Callable, Literal, Protocol, Any, overload

from .typing import Contexts

SCOPE = Literal["prepare", "parsing", "complete", "cleanup"]


class AuxType(Enum):
    supply = auto()
    judge = auto()
    depend = auto()


class CombineMode(Enum):
    AND = auto()
    OR = auto()
    SINGLE = auto()


@dataclass(init=False, eq=True, unsafe_hash=True)
class BaseAuxiliary(metaclass=ABCMeta):
    type: AuxType
    mode: CombineMode

    @property
    @abstractmethod
    def available_scopes(self) -> set[SCOPE]:
        raise NotImplementedError

    def __init__(self, atype: AuxType, mode: CombineMode = CombineMode.SINGLE):
        self.type = atype
        self.mode = mode

    @abstractmethod
    async def __call__(self, scope: SCOPE, context: Contexts):
        raise NotImplementedError


class SupplyAuxiliary(BaseAuxiliary):
    def __init__(self, mode: CombineMode = CombineMode.SINGLE):
        super().__init__(AuxType.supply, mode)

    @abstractmethod
    async def __call__(self, scope: SCOPE, context: Contexts) -> Optional[Contexts]:
        raise NotImplementedError


class JudgeAuxiliary(BaseAuxiliary):
    def __init__(self, mode: CombineMode = CombineMode.SINGLE):
        super().__init__(AuxType.judge, mode)

    @abstractmethod
    async def __call__(self, scope: SCOPE, context: Contexts) -> Optional[bool]:
        raise NotImplementedError


class Executor(Protocol):
    async def __call__(self, scope: SCOPE, context: Contexts): ...


class CombineExecutor:
    steps: list[Callable[[SCOPE, Contexts], Awaitable]]

    def __init__(self, auxes: list[BaseAuxiliary]):
        self.steps = []
        ors = []

        async def _ors(_scope: SCOPE, ctx: Contexts, *, funcs: list[BaseAuxiliary]):
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

    async def __call__(self, scope: SCOPE, context: Contexts) -> Optional[bool]:
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
    mode: CombineMode,
    prepare: Callable[[Contexts], Optional[Contexts]] | None = None,
    complete: Callable[[Contexts], Optional[Contexts]] | None = None,
    cleanup: Callable[[Contexts], Optional[Contexts]] | None = None,
): ...


@overload
def auxilia(
    atype: Literal[AuxType.judge],
    mode: CombineMode,
    prepare: Callable[[Contexts], Optional[bool]] | None = None,
    complete: Callable[[Contexts], Optional[bool]] | None = None,
    cleanup: Callable[[Contexts], Optional[bool]] | None = None,
): ...


def auxilia(
    atype: AuxType,
    mode: CombineMode,
    prepare: Callable[[Contexts], Any] | None = None,
    complete: Callable[[Contexts], Any] | None = None,
    cleanup: Callable[[Contexts], Any] | None = None,
):
    class _Auxiliary(BaseAuxiliary):
        async def __call__(self, scope: SCOPE, context: Contexts):
            res = None
            if scope == "prepare" and prepare:
                res = prepare(context)
            if scope == "complete" and complete:
                res = complete(context)
            if scope == "cleanup" and cleanup:
                res = cleanup(context)
            return res if res is False else context

        @property
        def available_scopes(self) -> set[SCOPE]:
            return {"prepare", "complete", "cleanup"}

    return _Auxiliary(atype, mode)
