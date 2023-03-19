from __future__ import annotations

import inspect
import functools
from dataclasses import dataclass
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any, Generic, TypeVar, Callable, Mapping

from typing_extensions import TypeAlias

Collection: TypeAlias = "dict[str, Any]"


T = TypeVar("T")
TCallable = TypeVar("TCallable", bound=Callable[..., Any])
D = TypeVar("D")
Empty = inspect.Signature.empty


class ContextModel(Generic[T]):
    current_ctx: ContextVar[T]

    def __init__(self, name: str) -> None:
        self.current_ctx = ContextVar(name)

    def get(self, default: T | D | None = None) -> T | D:
        return self.current_ctx.get(default)

    def set(self, value: T):
        return self.current_ctx.set(value)

    def reset(self, token: Token):
        return self.current_ctx.reset(token)

    @contextmanager
    def use(self, value: T):
        token = self.set(value)
        yield
        self.reset(token)


try:
    from inspect import get_annotations  # type: ignore
except ImportError:

    def get_annotations(
        obj: Callable,
        *,
        _globals: Mapping[str, Any] | None = None,
        _locals: Mapping[str, Any] | None = None,
        eval_str: bool = False,
    ) -> dict[str, Any]:  # sourcery skip: avoid-builtin-shadow
        if not callable(obj):
            raise TypeError(f"{obj!r} is not a module, class, or callable.")

        ann = getattr(obj, "__annotations__", None)
        obj_globals = getattr(obj, "__globals__", None)
        obj_locals = None
        unwrap = obj
        if ann is None:
            return {}

        if not isinstance(ann, dict):
            raise ValueError(f"{unwrap!r}.__annotations__ is neither a dict nor None")
        if not ann:
            return {}

        if not eval_str:
            return dict(ann)

        if unwrap is not None:
            while True:
                if hasattr(unwrap, "__wrapped__"):
                    unwrap = unwrap.__wrapped__
                    continue
                if isinstance(unwrap, functools.partial):
                    unwrap = unwrap.func
                    continue
                break
            if hasattr(unwrap, "__globals__"):
                obj_globals = unwrap.__globals__

        if _globals is None:
            _globals = obj_globals
        if _locals is None:
            _locals = obj_locals

        return {key: eval(value, _globals, _locals) if isinstance(value, str) else value for key, value in ann.items()}  # type: ignore


@dataclass
class Force:
    """用于转义在本框架中特殊部分的特殊值"""
    value: Any
