from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, TypeVar, Union


class Contexts(Dict[str, Any]):
    ...


T = TypeVar("T")
TCallable = TypeVar("TCallable", bound=Callable[..., Any])
TTarget = Union[Callable[..., T], Callable[..., Awaitable[T]]]


@dataclass
class Force:
    """用于转义在本框架中特殊部分的特殊值"""

    value: Any
