from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, TypeVar, Union


class Contexts(Dict[str, Any]):
    ...


T = TypeVar("T")
TTarget = Union[Callable[...,  Awaitable[T]], Callable[..., T]]
TCallable = TypeVar("TCallable", bound=TTarget[Any])


@dataclass
class Force:
    """用于转义在本框架中特殊部分的特殊值"""

    value: Any
