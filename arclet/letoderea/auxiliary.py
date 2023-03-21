from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    TypeVar,
    Union,
    overload,
)


from .event import BaseEvent
from .exceptions import JudgementError
from .typing import Contexts
from .utils import run_always_await

if TYPE_CHECKING:
    from .subscriber import Subscriber


class Scope(Enum):
    before_parse = auto()
    parsing = auto()
    after_parse = auto()
    cleanup = auto()


class AuxType(Enum):
    supply = auto()
    judge = auto()


TAux = TypeVar("TAux", bound="BaseAuxiliary")
TTarget = TypeVar("TTarget", bound=Union[Callable, "Subscriber"])
supply = Callable[["BaseAuxiliary", Contexts], Any]
judge = Callable[["BaseAuxiliary", BaseEvent], bool]


@dataclass
class AuxHandler:
    """
    参数辅助器基类，用于修饰参数, 或者判断条件
    """

    scope: Scope
    aux_type: AuxType
    handler: Union[supply, judge]

    async def supply(self, source: "BaseAuxiliary", context: Contexts):
        h: supply = self.handler  # type: ignore
        return await run_always_await(h, source, context)

    async def judge(self, source: "BaseAuxiliary", event: BaseEvent):
        h: judge = self.handler  # type: ignore
        if await run_always_await(h, source, event) is False:
            raise JudgementError


_local_storage: dict[type["BaseAuxiliary"], dict[Scope, list["AuxHandler"]]] = {}


class BaseAuxiliary:
    handlers: dict[Scope, list["AuxHandler"]]

    def __init__(self):
        self.handlers = {}
        if _local_storage.get(self.__class__):
            self.handlers.update(_local_storage.get(self.__class__, {}))

    @overload
    def set(
        self, scope: Scope, atype: Literal[AuxType.supply]
    ) -> Callable[[Callable[[TAux, Contexts], Any]], Callable[[TAux, Contexts], Any]]:
        ...

    @overload
    def set(
        self, scope: Scope, atype: Literal[AuxType.judge]
    ) -> Callable[[Callable[[TAux, BaseEvent], bool]], Callable[[TAux, BaseEvent], bool]]:
        ...

    def set(self, scope: Scope, atype: AuxType):  # type: ignore
        def decorator(func: Callable):
            self.handlers.setdefault(scope, []).append(AuxHandler(scope, atype, func))
            return func

        return decorator

    @classmethod
    @overload
    def inject(
        cls, scope: Scope, atype: Literal[AuxType.supply]
    ) -> Callable[[Callable[[TAux, Contexts], Any]], Callable[[TAux, Contexts], Any]]:
        ...

    @classmethod
    @overload
    def inject(
        cls, scope: Scope, atype: Literal[AuxType.judge]
    ) -> Callable[[Callable[[TAux, BaseEvent], bool]], Callable[[TAux, BaseEvent], bool]]:
        ...

    @classmethod
    def inject(cls, scope: Scope, atype: AuxType):  # type: ignore
        def decorator(func: Callable):
            _local_storage.setdefault(cls, {}).setdefault(scope, []).append(
                AuxHandler(scope, atype, func)
            )
            return func

        return decorator

    def __eq__(self, other: "BaseAuxiliary"):
        return self.handlers == other.handlers
