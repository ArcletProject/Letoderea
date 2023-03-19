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
        return cls

    def __enter__(self):
        _record_locals.update(inspect.stack()[1].frame.f_locals.copy())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _new_locals = inspect.stack()[1].frame.f_locals.copy()
        _diff = {k: v for k, v in _new_locals.items() if k not in _record_locals and v != self}
        _record_locals.clear()
        self.providers.extend(list(_diff.values()))


class BaseEvent(metaclass=EventMeta):
    @abstractmethod
    async def gather(self, collection: Collection):
        raise NotImplementedError
