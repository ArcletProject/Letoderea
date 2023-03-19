from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Literal,
    TypeVar,
    Union,
    overload,
)

from typing_extensions import Self

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


TTarget = TypeVar("TTarget", bound=Union[Callable, "Subscriber"])
TAux = TypeVar("TAux", bound="BaseAuxiliary")
supply = Callable[["Package"], Any]
judge = Callable[["BaseAuxiliary", BaseEvent], bool]


@dataclass
class Package(Generic[TAux]):
    source: TAux
    name: str
    value: Any
    annotation: Any


@dataclass
class AuxHandler:
    """
    参数辅助器基类，用于修饰参数, 或者判断条件
    """

    scope: Scope
    aux_type: AuxType
    handler: Union[supply, judge]

    async def supply(self, source: Self, arg_type: Any, collection: Contexts):
        h: supply = self.handler
        for k, v in collection.items():
            arg = await run_always_await(h, Package(source, k, v, arg_type))  # type: ignore
            if arg is None:
                continue
            collection[k] = arg

    async def judge(self, source: Self, event: BaseEvent):
        h: judge = self.handler
        if await run_always_await(h, source, event) is False:
            raise JudgementError


_local_storage: dict[type["BaseAuxiliary"], dict[Scope, list["AuxHandler"]]] = {}


class BaseAuxiliary:
    handlers: dict[Scope, list["AuxHandler"]]

    def __init__(self):
        self.handlers = {}
        if _local_storage.get(self.__class__):
            self.handlers.update(_local_storage.pop(self.__class__))

    @overload
    def set(
        self, scope: Scope, atype: Literal[AuxType.supply]
    ) -> Callable[[supply], supply]:
        ...

    @overload
    def set(
        self, scope: Scope, atype: Literal[AuxType.judge]
    ) -> Callable[[judge], judge]:
        ...

    def set(self, scope: Scope, atype: AuxType):
        def decorator(func: Callable):
            self.handlers.setdefault(scope, []).append(AuxHandler(scope, atype, func))
            return func

        return decorator

    @classmethod
    @overload
    def inject(
        cls, scope: Scope, atype: Literal[AuxType.supply]
    ) -> Callable[[supply], supply]:
        ...

    @classmethod
    @overload
    def inject(
        cls, scope: Scope, atype: Literal[AuxType.judge]
    ) -> Callable[[judge], judge]:
        ...

    @classmethod
    def inject(cls, scope: Scope, atype: AuxType):
        def decorator(func: Callable):
            _local_storage.setdefault(cls, {}).setdefault(scope, []).append(
                AuxHandler(scope, atype, func)
            )
            return func

        return decorator

    @classmethod
    def wrap(cls, *args, **kwargs):
        def wrapper(target: TTarget) -> TTarget:
            _target = target if isinstance(target, Callable) else target.callable_target
            if not hasattr(_target, "__auxiliaries__"):
                setattr(_target, "__auxiliaries__", [cls(*args, **kwargs)])  # type: ignore
            else:
                getattr(_target, "__auxiliaries__").append(cls(*args, **kwargs))  # type: ignore
            return target

        return wrapper

    def __eq__(self, other: "BaseAuxiliary"):
        return self.handlers == other.handlers
