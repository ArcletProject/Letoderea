from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Coroutine
from contextvars import copy_context
from dataclasses import dataclass
from functools import partial, wraps
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable, Generator, Generic, Protocol, TypeVar, Union, overload
from typing_extensions import ParamSpec, Self, TypeGuard

T = TypeVar("T")
T1 = TypeVar("T1")


class CtxItem(Generic[T]):
    ...


class Contexts(dict[str, Any]):
    if TYPE_CHECKING:

        def copy(self) -> Self: ...

        @overload
        def __getitem__(self, item: CtxItem[T1]) -> T1: ...

        @overload
        def __getitem__(self, item: str) -> Any: ...

        def __getitem__(self, item: Union[str, CtxItem[T1]]) -> Any: ...

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

        def get(self, __key: Union[str, CtxItem[T1]], __default: Any = ...) -> Any: ...  # type: ignore
    ...


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


class Resultable(Protocol[T]):
    __result_type__: type[T]


def run_sync(call: Callable[P, T]) -> Callable[P, Coroutine[None, None, T]]:
    """一个用于包装 sync function 为 async function 的装饰器

    参数:
        call: 被装饰的同步函数
    """

    @wraps(call)
    async def _wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        loop = asyncio.get_running_loop()
        pfunc = partial(call, *args, **kwargs)
        context = copy_context()
        result = await loop.run_in_executor(None, partial(context.run, pfunc))
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
