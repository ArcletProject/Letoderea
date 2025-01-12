from __future__ import annotations

from asyncio import Queue
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import is_dataclass
from typing import Any, Callable, Final, Protocol, TypeVar, cast, runtime_checkable

from tarina import generic_isinstance

from .provider import Provider, ProviderFactory, get_providers
from .typing import Contexts

T = TypeVar("T")


@runtime_checkable
class Publishable(Protocol):
    __publisher__: str


_publishers: dict[str, "Publisher"] = {}


class Publisher:
    id: str
    providers: list[Provider[Any] | ProviderFactory]

    def __init__(
        self,
        target: type[Any],
        id_: str | None = None,
        queue_size: int = -1,
    ):
        if id_:
            self.id = id_
        elif hasattr(target, "__publisher__"):
            self.id = target.__publisher__
        else:
            self.id = f"$event:{target.__name__}"
        self.target = target
        self.event_queue = Queue(queue_size)
        self.providers = [*get_providers(target)]
        _publishers[self.id] = self

    def __repr__(self):
        return f"{self.__class__.__name__}::{self.id}"

    def unsafe_push(self, event: Any) -> None:
        """将事件放入队列，等待被 event system 主动轮询; 该方法可能引发 QueueFull 异常"""
        self.event_queue.put_nowait(event)

    async def push(self, event: Any):
        """将事件放入队列，等待被 event system 主动轮询"""
        await self.event_queue.put(event)

    async def supply(self) -> Any:
        """被动提供事件方法， 由 event system 主动轮询"""
        return await self.event_queue.get()

    def bind(
        self,
        *args: Provider | type[Provider] | ProviderFactory | type[ProviderFactory],
    ) -> None:
        """为发布器增加间接 Provider 或 Auxiliaries"""
        self.providers.extend(p() if isinstance(p, type) else p for p in args)

    def unbind(
        self,
        arg: Provider | type[Provider] | ProviderFactory | type[ProviderFactory],
    ) -> None:
        """移除发布器的间接 Provider 或 Auxiliaries"""
        if isinstance(arg, (ProviderFactory, Provider)):
            with suppress(ValueError):
                self.providers.remove(arg)
        else:
            for p in self.providers.copy():
                if isinstance(p, arg):
                    self.providers.remove(p)

    def validate(self, event):
        return isinstance(event, self.target)

    def dispose(self):
        _publishers.pop(self.id, None)


def _supplier(event: Any) -> dict[str, Any]:
    if isinstance(event, dict):
        return event
    if is_dataclass(event):
        return vars(event)
    return {}


class __BackendPublisher(Publisher):
    def __init__(self):
        self.id = "$backend"
        self.providers = []
        self.auxiliaries = []

    def validate(self, event):
        return True


_backend_publisher: Final[__BackendPublisher] = __BackendPublisher()


class ExternalPublisher(Publisher):
    """宽松的发布器，任意对象都可以作为事件被发布"""

    def __init__(
        self,
        target: type[T],
        id_: str | None = None,
        supplier: Callable[[T], Mapping[str, Any]] | None = None,
        queue_size: int = -1,
    ):
        super().__init__(target, id_, queue_size=queue_size)

        async def _(event):
            data = {"$event": event, **((supplier or _supplier)(event))}
            data = {k: v for k, v in data.items() if not k.startswith("_")}
            return cast(Contexts, data)

        self.external_gather = _

    def validate(self, event):
        return generic_isinstance(event, self.target)


def filter_publisher(target: type[Any]):
    if hasattr(target, "__publisher__"):
        label = target.__publisher__
    else:
        label = f"$event:{target.__name__}"
    if label in _publishers:
        return _publishers[label]
    for pub in _publishers.values():
        if pub.target is target:
            return pub


def search_publisher(event: Any) -> Publisher:
    if hasattr(event, "__publisher__") and (pub := _publishers.get(event.__publisher__)):
        return pub
    if pub := _publishers.get(f"$event:{type(event).__name__}"):
        return pub
    return next((pub for pub in _publishers.values() if pub.validate(event)), _backend_publisher)
