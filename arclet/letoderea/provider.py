from __future__ import annotations

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Generic, TypeVar

from .typing import Contexts

T = TypeVar("T")


class ProvideMode(Enum):
    """提供模式"""

    strict = auto()
    subclass = auto()
    generic = auto()
    wildcard = auto()


_local_storage: dict[type["Provider"], tuple[str, type, ProvideMode]] = {}


@dataclass(init=False, repr=True)
class Provider(Generic[T], metaclass=ABCMeta):
    target: str
    origin: type[T]
    mode: ProvideMode

    def __init__(self):
        self.target = _local_storage[self.__class__][0]
        self.origin = _local_storage[self.__class__][1]  # type: ignore
        self.mode = _local_storage[self.__class__][2]

    def __init_subclass__(cls, **kwargs):
        _local_storage[cls] = (
            kwargs.get("target", "$"),
            cls.__orig_bases__[0].__args__[0],  # type: ignore
            kwargs.get("mode", ProvideMode.strict),
        )
        if (
            _local_storage[cls][1] is T
            and _local_storage[cls][2] is not ProvideMode.wildcard
        ):
            raise TypeError("Subclass of Provider must be generic")

    @abstractmethod
    async def __call__(self, context: Contexts) -> T | None:
        """
        依据提供模式，从集合中提供一个对象
        """
        raise NotImplementedError
