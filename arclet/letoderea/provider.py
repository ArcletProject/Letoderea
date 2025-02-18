from __future__ import annotations

import inspect
from abc import ABCMeta, abstractmethod
from collections.abc import Awaitable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, ClassVar, Generic, NamedTuple, TypeVar

from tarina import generic_issubclass, run_always_await
from tarina.generic import get_origin

from .event import EVENT
from .typing import Contexts

T = TypeVar("T")


class Param(NamedTuple):
    name: str
    annotation: Any
    default: Any
    is_empty: bool


_local_storage: dict[type["Provider"], type] = {}


@dataclass(init=False, repr=True)
class Provider(Generic[T], metaclass=ABCMeta):
    priority: ClassVar[int] = 20
    origin: type[T]

    def __init__(self):
        self.origin = _local_storage[self.__class__]  # type: ignore

    def __init_subclass__(cls, **kwargs):
        _local_storage[cls] = cls.__orig_bases__[0].__args__[0]  # type: ignore
        if _local_storage[cls] is T:
            raise TypeError("Subclass of Provider must be generic. If you need a wildcard, please using `typing.Any`")

    def validate(self, param: Param):
        anno = get_origin(param.annotation)
        return (
            self.origin == param.annotation
            or (isinstance(anno, type) and anno is not bool and generic_issubclass(anno, self.origin))
            or (
                not (self.origin is bool and generic_issubclass(anno, int))
                and generic_issubclass(self.origin, param.annotation)
            )
        )

    @abstractmethod
    async def __call__(self, context: Contexts) -> T | None:
        """
        依据提供模式，从集合中提供一个对象
        """
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
            return validate(param) if validate else param.name == target if target else super().validate(param)

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
        """
        依据参数类型自行分配对应 Provider
        """


@lru_cache(4096)
def get_providers(
    event: Any,
) -> list[Provider[Any] | ProviderFactory]:
    res = []
    for cls in reversed(event.__mro__[:-1]):  # type: ignore
        res.extend(getattr(cls, "providers", []))
    res.extend(
        p
        for _, p in inspect.getmembers(
            event,
            lambda x: inspect.isclass(x) and issubclass(x, (Provider, ProviderFactory)),
        )
    )
    providers = [p() if isinstance(p, type) else p for p in res]
    return list({p.__class__: p for p in providers}.values())


global_providers: list[Provider | ProviderFactory | type[Provider] | type[ProviderFactory]] = []


class EventProvider(Provider[Any]):
    EVENT_CLASS: ClassVar[type | None] = None

    def validate(self, param: Param):
        if param.name == "event":
            return True
        if self.EVENT_CLASS:
            return isinstance(param.annotation, type) and issubclass(param.annotation, self.EVENT_CLASS)
        return False

    async def __call__(self, context: Contexts):
        return context.get(EVENT)


class ContextProvider(Provider[Contexts]):
    def validate(self, param: Param):
        return param.annotation is Contexts

    async def __call__(self, context: Contexts) -> Contexts:
        return context


global_providers.extend([EventProvider(), ContextProvider()])
