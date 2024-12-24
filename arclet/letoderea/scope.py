from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from secrets import token_urlsafe
from typing import Any, Callable, TypeVar, overload

from .auxiliary import BaseAuxiliary, global_auxiliaries
from .context import scope_ctx
from .handler import dispatch
from .provider import Provider, ProviderFactory, global_providers
from .subscriber import Subscriber
from .publisher import Publisher, search_publisher, _backend_publisher, _publishers
from .typing import Result, Resultable


T = TypeVar("T")


class Scope:
    id: str
    subscribers: dict[str, Subscriber]
    lookup_map: dict[str, set[str]]

    def __init__(
        self,
        id_: str | None = None,
    ):
        self.id = id_ or token_urlsafe(16)
        self.subscribers = {}
        self.lookup_map = {}
        self.available = True

    def __repr__(self):
        return f"{self.__class__.__name__}::{self.id}"

    async def emit(self, event: Any) -> None:
        """主动向自己的订阅者发布事件"""
        await dispatch(self.subscribers.values(), event)

    @overload
    async def bail(self, event: Resultable[T]) -> Result[T] | None: ...

    @overload
    async def bail(self, event: Any) -> Result[Any] | None: ...

    async def bail(self, event: Any) -> Result | None:
        """主动向自己的订阅者发布事件, 并返回结果"""
        return await dispatch(self.subscribers.values(), event, return_result=True)

    def add_subscriber(self, subscriber: Subscriber) -> None:
        """
        添加订阅者
        """
        self.subscribers[subscriber.id] = subscriber

    def remove_subscriber(self, subscriber: Subscriber) -> None:
        """
        移除订阅者
        """
        self.subscribers.pop(subscriber.id, None)
        self.lookup_map.pop(subscriber.id, None)

    @contextmanager
    def context(self):
        token = scope_ctx.set(self)
        try:
            yield self
        finally:
            scope_ctx.reset(token)

    @overload
    def register(
        self,
        func: Callable[..., Any],
        events: type | tuple[type, ...] | None = None,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        publisher: str | Publisher | None = None,
        temporary: bool = False,
    ) -> Subscriber: ...

    @overload
    def register(
        self,
        *,
        events: type | tuple[type, ...] | None = None,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        publisher: str | Publisher | None = None,
        temporary: bool = False,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    def register(
        self,
        func: Callable[..., Any] | None = None,
        events: type | tuple[type, ...] | None = None,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        publisher: str | Publisher | None = None,
        temporary: bool = False,
    ):
        """注册一个订阅者"""
        auxiliaries = auxiliaries or []
        providers = providers or []
        if isinstance(publisher, Publisher):
            pubs = [publisher]
        elif isinstance(publisher, str) and publisher in _publishers:
            pubs = [_publishers[publisher]]
        elif not events:
            pubs = [_backend_publisher]
        else:
            pubs = [*filter(None, (search_publisher(target) for target in (events if isinstance(events, tuple) else (events,))))]
        if not pubs:
            raise ValueError(f"No publisher found for events: {events}")
        pub_providers = [p for pub in pubs for p in pub.providers]
        pub_auxiliaries = [a for pub in pubs for a in pub.auxiliaries]

        def register_wrapper(exec_target: Callable, /) -> Subscriber:
            _providers = [
                *global_providers,
                *pub_providers,
                *providers,
            ]
            _auxiliaries = [
                *global_auxiliaries,
                *pub_auxiliaries,
                *auxiliaries,
            ]
            res = Subscriber(
                exec_target,
                priority=priority,
                auxiliaries=_auxiliaries,
                providers=_providers,
                dispose=self.remove_subscriber,
                temporary=temporary,
            )
            self.lookup_map[res.id] = {pub.id for pub in pubs}
            self.add_subscriber(res)
            return res

        if func:
            return register_wrapper(func)
        return register_wrapper

    def get_subscribers(self, publisher_id: str) -> list[Subscriber]:
        return [sub for id_, sub in self.subscribers.items() if publisher_id in self.lookup_map[id_] or _backend_publisher.id in self.lookup_map[id_]]

    def iter_subscribers(self, publisher_id: str):
        for id_, sub in self.subscribers.items():
            if publisher_id in self.lookup_map[id_] or _backend_publisher.id in self.lookup_map[id_]:
                yield sub
