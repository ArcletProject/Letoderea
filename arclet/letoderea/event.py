from __future__ import annotations

import inspect
from functools import lru_cache
from typing import Any, Protocol, TypeVar, runtime_checkable

from .auxiliary import BaseAuxiliary
from .provider import Provider, ProviderFactory
from .typing import Contexts


@runtime_checkable
class BaseEvent(Protocol):
    async def gather(self, context: Contexts) -> Any: ...


@lru_cache(4096)
def get_providers(
    event: Any,
) -> list[Provider | ProviderFactory]:
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


@lru_cache(4096)
def get_auxiliaries(event: Any) -> list[BaseAuxiliary]:
    res = []
    for cls in reversed(event.__mro__[:-1]):  # type: ignore
        res.extend(getattr(cls, "auxiliaries", []))
    res.extend(
        p
        for _, p in inspect.getmembers(
            event,
            lambda x: inspect.isclass(x) and issubclass(x, BaseAuxiliary),
        )
    )
    auxiliaries: list[BaseAuxiliary] = [a() if isinstance(a, type) else a for a in res]
    return list({a.id: a for a in auxiliaries}.values())


C = TypeVar("C")


def make_event(cls: type[C]) -> type[C]:
    if not hasattr(cls, "__annotations__"):
        raise ValueError(f"@make_event can only take effect for class with attribute annotations, not {cls}")

    async def _gather(self, context: Contexts):
        for key in cls.__annotations__:
            if key in ("providers", "auxiliaries"):
                continue
            context[key] = getattr(self, key, None)

    cls.gather = _gather  # type: ignore
    return cls  # type: ignore
