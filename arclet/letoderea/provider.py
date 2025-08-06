from __future__ import annotations

import inspect
from abc import ABCMeta, abstractmethod
from contextlib import AsyncExitStack
from collections.abc import Awaitable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, ClassVar, Generic, NamedTuple, Sequence, TypeVar
from typing_extensions import TypeAlias

from tarina import generic_issubclass, run_always_await
from tarina.generic import get_origin, is_optional, origin_is_union

from .typing import Contexts, EVENT

T = TypeVar("T")


class Param(NamedTuple):
    name: str
    annotation: Any
    default: Any
    is_empty: bool


@dataclass(init=False, repr=True)
class Provider(Generic[T], metaclass=ABCMeta):
    priority: ClassVar[int] = 20
    origin: type[T]

    def __init__(self):
        self.origin = self.__class__.__orig_bases__[0].__args__[0]  # type: ignore

    def __init_subclass__(cls, **kwargs):
        if cls.__orig_bases__[0].__args__[0] is T:  # type: ignore
            raise TypeError("Subclass of Provider must be generic. If you need a wildcard, please using `typing.Any`")

    def validate(self, param: Param):
        anno = get_origin(param.annotation)
        if self.origin is bool:
            return generic_issubclass(anno, bool)
        return self.origin == param.annotation or (
            generic_issubclass(param.annotation, self.origin)
            or is_optional(param.annotation, self.origin)
            or (origin_is_union(anno) and generic_issubclass(self.origin, param.annotation))
        )

    @abstractmethod
    async def __call__(self, context: Contexts) -> T | None:
        """依据提供模式，从集合中提供一个对象"""
        raise NotImplementedError


def provide(
    origin: type[T],
    target: str | None = None,
    call: Callable[[Contexts], T | None | Awaitable[T | None]] | str | None = None,
    validate: Callable[[Param], bool] | None = None,
    priority: int = 20,
    _id: str = "_Provider",
) -> Provider[T]:
    """
    用于动态生成 Provider 的装饰器
    """
    if not call and not target:
        raise ValueError("Either `call` or `target` must be provided")

    class _Provider(Provider[origin]):
        def validate(self, param: Param):
            if validate:
                return validate(param)
            if param.annotation:
                return super().validate(param) and (not target or param.name == target)
            return param.name == target

        async def __call__(self, context: Contexts):
            if not call and target:
                return context.get(target)
            if isinstance(call, str):
                return context.get(call)
            return await run_always_await(call, context)  # type: ignore

        def __repr__(self):
            return f"{_id.title()}(origin={origin}{(', target=' + repr(target)) if target else ''})"

    _Provider.priority = priority
    return type(_id, (_Provider,), {})()


class ProviderFactory(metaclass=ABCMeta):
    @abstractmethod
    def validate(self, param: Param) -> Provider | None:
        """依据参数类型自行分配对应 Provider"""


@lru_cache
def get_providers(event: Any) -> list[Provider[Any] | ProviderFactory]:
    res = [p for cls in reversed(event.__mro__[:-1]) for p in getattr(cls, "providers", [])]  # type: ignore
    res.extend(p for _, p in inspect.getmembers(event, lambda x: inspect.isclass(x) and issubclass(x, (Provider, ProviderFactory))))
    providers = [p() if isinstance(p, type) else p for p in res]
    return list({p.__class__: p for p in providers}.values())


global_providers: list[Provider | ProviderFactory | type[Provider] | type[ProviderFactory]] = []


class EventProvider(Provider[Any]):
    EVENT_CLASS: ClassVar[type | None] = None

    def validate(self, param: Param):
        if param.name == "event":
            return True
        if self.EVENT_CLASS:
            return generic_issubclass(param.annotation, self.EVENT_CLASS) or is_optional(param.annotation, self.EVENT_CLASS)
        return False

    async def __call__(self, context: Contexts):
        return context.get(EVENT)


class ContextProvider(Provider[Contexts]):
    def validate(self, param: Param):
        return param.annotation is Contexts or is_optional(param.annotation, Contexts)

    async def __call__(self, context: Contexts) -> Contexts:
        return context


class AsyncExitStackProvider(Provider[AsyncExitStack]):
    def validate(self, param: Param):
        return param.annotation is AsyncExitStack or is_optional(param.annotation, AsyncExitStack)

    async def __call__(self, context: Contexts):
        return context.get("$exit_stack")


global_providers.extend([EventProvider(), ContextProvider(), AsyncExitStackProvider()])
TProviders: TypeAlias = "Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]]"
