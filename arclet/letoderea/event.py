from __future__ import annotations

from abc import ABCMeta, abstractmethod
import inspect
from .typing import Collection
from .provider import Provider

_record_locals = {}


class EventMeta(ABCMeta):
    providers: list[type[Provider] | Provider]

    def __new__(mcs, name, bases, namespace, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        cls.providers = getattr(cls, "providers", [])
        cls.providers.extend(
            p for _, p in inspect.getmembers(
                cls,
                lambda x: inspect.isclass(x)
                and issubclass(x, Provider)
                and x is not Provider,
            )
        )
        return cls


class BaseEvent(metaclass=EventMeta):
    @abstractmethod
    async def gather(self, collection: Collection):
        raise NotImplementedError
