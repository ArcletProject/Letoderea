from __future__ import annotations

from typing import Any, Protocol, Final, TypeVar, runtime_checkable

from .typing import Contexts, CtxItem
from .publisher import Publisher


@runtime_checkable
class BaseEvent(Protocol):
    async def gather(self, context: Contexts) -> Any: ...


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
    _ = Publisher(cls)
    return cls  # type: ignore


EVENT: Final[CtxItem[BaseEvent]] = CtxItem("event")
