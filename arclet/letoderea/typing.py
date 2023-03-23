from __future__ import annotations

import contextlib
import functools
import inspect
import sys
import types
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    Mapping,
    TypeVar,
    Union,
)

from typing_extensions import Annotated, get_args, get_origin

if TYPE_CHECKING:
    from types import GenericAlias  # noqa
else:
    GenericAlias: type = type(List[int])
AnnotatedType: type = type(Annotated[int, lambda x: x > 0])
Unions = (
    (Union, types.UnionType) if sys.version_info >= (3, 10) else (Union,)
)  # pragma: no cover


class Contexts(Dict[str, Any]):
    ...


T = TypeVar("T")
TCallable = TypeVar("TCallable", bound=Callable[..., Any])
TTarget = Union[Callable[..., T], Callable[..., Awaitable[T]]]
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


def generic_isinstance(obj: Any, par: type | Any | tuple[type, ...]) -> bool:
    """
    检查 obj 是否是 par 中的一个类型, 支持泛型, Any, Union, GenericAlias
    """
    if par is Any:
        return True
    with contextlib.suppress(TypeError):
        if isinstance(par, AnnotatedType):
            return generic_isinstance(obj, get_args(par)[0])
        if isinstance(par, type):
            return isinstance(obj, par)
        if get_origin(par) is Literal:
            return obj in get_args(par)
        if get_origin(par) in Unions:  # pragma: no cover
            return any(generic_isinstance(obj, p) for p in get_args(par))
        if isinstance(par, TypeVar):  # pragma: no cover
            if par.__constraints__:
                return any(generic_isinstance(obj, p) for p in par.__constraints__)
            return generic_isinstance(obj, par.__bound__) if par.__bound__ else True
        if isinstance(par, tuple):
            return any(generic_isinstance(obj, p) for p in par)
        if isinstance(obj, get_origin(par)):  # type: ignore
            return True
    return False
