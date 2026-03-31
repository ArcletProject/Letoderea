from __future__ import annotations

import inspect
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar
from collections.abc import Callable

from tarina import is_async


T = TypeVar("T")

TTarget = Callable[..., Awaitable[T]] | Callable[..., T]
TCallable = TypeVar("TCallable", bound=Callable[..., Any])
TDispose = Callable[[], None]


@dataclass(slots=True)
class Force:
    """用于转义在本框架中特殊部分的特殊值"""

    value: Any


class Result(Generic[T]):
    """用于标记一个事件响应器的处理结果，通常应用在某个事件响应器的处理结果需要被事件发布者使用的情况"""
    __slots__ = ("value",)

    def __init__(self, value: T):
        self.value = value


class Resultable(Protocol[T]):
    def check_result(self, value: Any) -> Result[T] | None: ...


async def run_always_await(target: Callable[..., Any] | Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
    obj = target(*args, **kwargs)
    if is_async(target) or inspect.isawaitable(obj):
        obj = await obj  # type: ignore
    return obj
