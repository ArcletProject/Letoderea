from __future__ import annotations

from abc import ABCMeta, abstractmethod
from enum import Enum, auto
from typing import Generic, TypeVar, ClassVar

from .typing import Collection

T = TypeVar("T")


class ProvideMode(Enum):
    """提供模式"""

    wildcard = auto()
    subclass = auto()
    generic = auto()
    strict = auto()


class Provider(Generic[T], metaclass=ABCMeta):
    name: ClassVar[str]
    origin: type[T]
    mode: ClassVar[ProvideMode]

    def __init_subclass__(cls, **kwargs):
        if name := kwargs.get("name", "$"):
            cls.name = name
        if (mode := kwargs.get("mode", ProvideMode.strict)) and isinstance(mode, ProvideMode):
            cls.mode = mode
        cls.origin = cls.__orig_bases__[0].__args__[0]  # noqa
        if cls.origin is T and cls.mode is not ProvideMode.wildcard:
            raise TypeError("Subclass of Provider must be generic")

    @abstractmethod
    async def __call__(self, collection: Collection) -> T | None:
        """
        依据提供模式，从集合中提供一个对象
        """
        raise NotImplementedError
