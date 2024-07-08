from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from contextvars import copy_context
from dataclasses import dataclass
from functools import partial, wraps
from typing import Any, Awaitable, Callable, Dict, TypeVar, Union
from typing_extensions import ParamSpec


class Contexts(Dict[str, Any]):
    ...


T = TypeVar("T")
TTarget = Union[Callable[..., Awaitable[T]], Callable[..., T]]
TCallable = TypeVar("TCallable", bound=TTarget[Any])
P = ParamSpec("P")


@dataclass
class Force:
    """用于转义在本框架中特殊部分的特殊值"""

    value: Any


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
