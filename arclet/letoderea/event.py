from __future__ import annotations

import inspect
from functools import lru_cache
from typing import Protocol, runtime_checkable

from .auxiliary import BaseAuxiliary
from .provider import Provider
from .typing import Contexts


@runtime_checkable
class BaseEvent(Protocol):
    async def gather(self, context: Contexts):
        ...


@lru_cache(4096)
def get_providers(
    event: type[BaseEvent] | BaseEvent,
) -> list[Provider]:
    res = getattr(event, "providers", [])
    res.extend(
        p
        for _, p in inspect.getmembers(
            event,
            lambda x: inspect.isclass(x)
            and issubclass(x, Provider)
            and x is not Provider,
        )
    )
    return [p() if isinstance(p, type) else p for p in res]


@lru_cache(4096)
def get_auxiliaries(event: type[BaseEvent] | BaseEvent) -> list[BaseAuxiliary]:
    res = getattr(event, "auxiliaries", [])
    res.extend(
        p
        for _, p in inspect.getmembers(
            event,
            lambda x: inspect.isclass(x)
            and issubclass(x, BaseAuxiliary)
            and x is not BaseAuxiliary,
        )
    )
    return res


def make_event(cls: type) -> type:
    async def _gather(self, context: Contexts):
        for key in cls.__annotations__:
            context[key] = getattr(self, key)

    cls.gather = _gather  # type: ignore
    return cls  # type: ignore
