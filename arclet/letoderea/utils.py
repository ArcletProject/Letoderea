import inspect
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Iterable

from .typing import TTarget, get_annotations


def group_dict(iterable: Iterable, key_callable: Callable[[Any], Any]):
    temp = {}
    for i in iterable:
        k = key_callable(i)
        temp.setdefault(k, []).append(i)
    return temp


@lru_cache(4096)
def argument_analysis(callable_target: Callable):
    callable_annotation = get_annotations(callable_target, eval_str=True)
    return [
        (
            name,
            (
                callable_annotation.get(name)
                if isinstance(param.annotation, str)
                else param.annotation
            )
            if param.annotation is not inspect.Signature.empty
            else None,
            param.default,
        )
        for name, param in inspect.signature(callable_target).parameters.items()
    ]


@lru_cache(4096)
def is_coroutinefunction(o):
    return inspect.iscoroutinefunction(o)


@lru_cache(4096)
def is_awaitable(o):
    return inspect.isawaitable(o)


@lru_cache(4096)
def is_async(o: Any):
    return is_coroutinefunction(o) or is_awaitable(o)


async def run_always_await(target: TTarget[Any], *args, **kwargs) -> Any:
    obj = target(*args, **kwargs)
    if is_async(target) or is_async(obj):
        obj = await obj
    return obj


@dataclass
class Force:
    """用于转义在本框架中特殊部分的特殊值"""

    value: Any
