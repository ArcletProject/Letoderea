from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Generic, Protocol, TypeVar, Union, overload, cast
from typing_extensions import ParamSpec, Self


T = TypeVar("T")
T1 = TypeVar("T1")


class CtxItem(Generic[T]): ...


class Contexts(dict[str, Any]):
    if TYPE_CHECKING:

        def copy(self) -> Self: ...

        @overload
        def __getitem__(self, item: CtxItem[T1]) -> T1: ...

        @overload
        def __getitem__(self, item: str) -> Any: ...

        def __getitem__(self, item: str | CtxItem[T1]) -> Any: ...

        @overload
        def get(self, __key: CtxItem[T1]) -> T1 | None: ...

        @overload
        def get(self, __key: str) -> Any | None: ...

        @overload
        def get(self, __key: CtxItem[T1], __default: T1) -> T1: ...

        @overload
        def get(self, __key: str, __default: Any) -> Any: ...

        @overload
        def get(self, __key: CtxItem[T1], __default: T) -> T1 | T: ...

        def get(self, __key: str | CtxItem[T1], __default: Any = ...) -> Any: ...  # type: ignore

    ...


EVENT: CtxItem[Any] = cast(CtxItem, "$event")


async def generate_contexts(
    event: T, supplier:  Callable[[T, Contexts], Awaitable[Contexts | None]] | None = None, inherit_ctx: Contexts | None = None
) -> Contexts:
    contexts: Contexts = {EVENT: event, "$depend_cache": {}}  # type: ignore
    if supplier:
        await supplier(event, contexts)
    elif (_gather := getattr(event, "__context_gather__", getattr(event, "gather", None))) is not None:
        await _gather(contexts)
    if inherit_ctx:
        inherit_ctx.update(contexts)
        return inherit_ctx
    return contexts


TTarget = Union[Callable[..., Awaitable[T]], Callable[..., T]]
TCallable = TypeVar("TCallable", bound=Callable[..., Any])
P = ParamSpec("P")


@dataclass
class Force:
    """用于转义在本框架中特殊部分的特殊值"""

    value: Any


@dataclass
class Result(Generic[T]):
    """用于标记一个事件响应器的处理结果，通常应用在某个事件响应器的处理结果需要被事件发布者使用的情况"""

    value: T


class Resultable(Protocol[T]):
    def check_result(self, value: Any) -> Result[T] | None: ...
