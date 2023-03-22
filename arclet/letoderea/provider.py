from __future__ import annotations

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, NamedTuple, TypeVar, get_origin, Callable, Awaitable

from .typing import Contexts
from .utils import run_always_await

T = TypeVar("T")


class Param(NamedTuple):
    name: str
    annotation: Any
    default: Any
    is_empty: bool


_local_storage: dict[type["Provider"], type] = {}


@dataclass(init=False, repr=True)
class Provider(Generic[T], metaclass=ABCMeta):
    origin: type[T]

    def __init__(self):
        self.origin = _local_storage[self.__class__]  # type: ignore

    def __init_subclass__(cls, **kwargs):
        _local_storage[cls] = cls.__orig_bases__[0].__args__[0]  # type: ignore
        if _local_storage[cls] is T:
            raise TypeError(
                "Subclass of Provider must be generic. If you need a wildcard, please using `typing.Any`"
            )

    def validate(self, param: Param):
        return self.origin == param.annotation or (
            isinstance(param.annotation, type)
            and issubclass(param.annotation, get_origin(self.origin) or self.origin)
        )

    @abstractmethod
    async def __call__(self, context: Contexts) -> T | None:
        """
        依据提供模式，从集合中提供一个对象
        """
        raise NotImplementedError


def provide(
    origin: type[T],
    call: Callable[[Contexts], T | None | Awaitable[T | None]] | None = None,
    validate: Callable[[Param], bool] | None = None,
    target: str | None = None,
) -> type[Provider[T]]:
    """
    用于动态生成 Provider 的装饰器
    """
    if not call and not target:
        raise ValueError("Either `call` or `target` must be provided")

    class _Provider(Provider[origin]):
        def validate(self, param: Param):
            return validate(param) if validate else param.name == target if target else super().validate(param)

        async def __call__(self, context: Contexts):
            return await run_always_await(call, context) if call else context.get(target)

    return _Provider
