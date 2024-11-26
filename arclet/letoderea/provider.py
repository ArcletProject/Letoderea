from __future__ import annotations

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Generic, NamedTuple, TypeVar
from collections.abc import Awaitable

from tarina import generic_issubclass, run_always_await
from tarina.generic import get_origin

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
            return f"Provider::{_id}(origin={origin})"

    _Provider.priority = priority
    return _Provider()


class ProviderFactory(metaclass=ABCMeta):
    @abstractmethod
    def validate(self, param: Param) -> Provider | None:
        """
        依据参数类型自行分配对应 Provider
        """
