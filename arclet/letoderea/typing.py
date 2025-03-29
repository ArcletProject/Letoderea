from __future__ import annotations

import asyncio
import inspect
from collections.abc import AsyncGenerator, Awaitable, Coroutine, Generator
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Generic, Protocol, TypeVar, TypedDict, Union, overload, cast
from typing_extensions import ParamSpec, Self, TypeGuard

from tarina import generic_isinstance


_TypedDictMeta = type(TypedDict.__mro_entries__(...)[0])  # type: ignore


def is_typed_dict(cls: Any) -> bool:
    return cls.__class__ is _TypedDictMeta


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
    contexts: Contexts = {EVENT: event}  # type: ignore
    if supplier:
        await supplier(event, contexts)
    elif (_gather := getattr(event, "__context_gather__", getattr(event, "gather", None))) is not None:
        await _gather(contexts)
    if inherit_ctx:
        inherit_ctx.update(contexts)
        return inherit_ctx
    return contexts


TTarget = Union[Callable[..., Awaitable[T]], Callable[..., T]]
TCallable = TypeVar("TCallable", bound=TTarget[Any])
P = ParamSpec("P")


@dataclass
class Force:
    """用于转义在本框架中特殊部分的特殊值"""

    value: Any


@dataclass
class Result(Generic[T]):
    """用于标记一个事件响应器的处理结果，通常应用在某个事件响应器的处理结果需要被事件发布者使用的情况"""

    value: T

    @staticmethod
    def check_result(event: Any, result: Result):
        if not hasattr(event, "__result_type__"):
            return result
        if generic_isinstance(result.value, event.__result_type__):
            return result
        return


class Resultable(Protocol[T]):
    __result_type__: type[T]


def run_sync(call: Callable[P, T]) -> Callable[P, Coroutine[None, None, T]]:
    """一个用于包装 sync function 为 async function 的装饰器

    参数:
        call: 被装饰的同步函数
    """

    @wraps(call)
    async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        result = await asyncio.to_thread(call, *args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    return _wrapper


def run_sync_generator(call: Callable[P, Generator[T]]) -> Callable[P, AsyncGenerator[T]]:
    """一个用于包装 sync generator function 为 async generator function 的装饰器"""

    def _next(it):
        try:
            return next(it)
        except StopIteration:
            raise StopAsyncIteration from None

    @wraps(call)
    async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> AsyncGenerator[T, None]:
        gen = call(*args, **kwargs)
        try:
            while True:
                yield await run_sync(_next)(gen)
        except StopAsyncIteration:
            return

    return _wrapper


def is_gen_callable(call: Callable[..., Any]) -> TypeGuard[Callable[..., Generator]]:
    """检查 call 是否是一个生成器函数"""
    if inspect.isgeneratorfunction(call):
        return True
    func_ = getattr(call, "__call__", None)
    return inspect.isgeneratorfunction(func_)


def is_async_gen_callable(call: Callable[..., Any]) -> TypeGuard[Callable[..., AsyncGenerator]]:
    """检查 call 是否是一个异步生成器函数"""
    if inspect.isasyncgenfunction(call):
        return True
    func_ = getattr(call, "__call__", None)
    return inspect.isasyncgenfunction(func_)
