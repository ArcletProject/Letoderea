from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager, suppress
from secrets import token_urlsafe
from typing import Any, Callable, TypeVar, overload

from .context import scope_ctx
from .handler import dispatch
from .provider import Provider, ProviderFactory, global_providers
from .publisher import Publisher, _backend_publisher, _publishers, filter_publisher, search_publisher
from .subscriber import Propagator, Subscriber
from .typing import Result, Resultable

T = TypeVar("T")

_scopes: dict[str, Scope] = {}


class Scope:
    id: str
    subscribers: dict[str, tuple[Subscriber, set[str]]]
    providers: list[Provider[Any] | ProviderFactory]
    propagators: list[Propagator]

    def __init__(
        self,
        id_: str | None = None,
    ):
        self.id = id_ or token_urlsafe(16)
        self.subscribers = {}
        self.available = True
        self.providers = []
        self.propagators = []

    def __repr__(self):
        return f"{self.__class__.__name__}::{self.id}"

    async def emit(self, event: Any) -> None:
        """主动向自己的订阅者发布事件"""
        await dispatch(
            self.iter_subscribers(search_publisher(event).id),
            event,
        )

    @overload
    async def bail(self, event: Resultable[T]) -> Result[T] | None: ...

    @overload
    async def bail(self, event: Any) -> Result[Any] | None: ...

    async def bail(self, event: Any) -> Result | None:
        """主动向自己的订阅者发布事件, 并返回结果"""
        return await dispatch(self.iter_subscribers(search_publisher(event).id), event, return_result=True)

    def bind(
        self,
        *args: Provider | type[Provider] | ProviderFactory | type[ProviderFactory],
    ) -> None:
        """增加间接 Provider"""
        self.providers.extend(p() if isinstance(p, type) else p for p in args)

    def unbind(
        self,
        arg: Provider | type[Provider] | ProviderFactory | type[ProviderFactory],
    ) -> None:
        """移除间接 Provider"""
        if isinstance(arg, (ProviderFactory, Provider)):
            with suppress(ValueError):
                self.providers.remove(arg)
        else:
            for p in self.providers.copy():
                if isinstance(p, arg):
                    self.providers.remove(p)

    @contextmanager
    def context(self):
        token = scope_ctx.set(self)
        try:
            yield self
        finally:
            scope_ctx.reset(token)

    def remove_subscriber(self, subscriber: Subscriber) -> None:
        """
        移除订阅者
        """
        self.subscribers.pop(subscriber.id, None)

    @overload
    def register(
        self,
        func: Callable[..., Any],
        events: type | tuple[type, ...] | None = None,
        *,
        priority: int = 16,
        providers: Sequence[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
        publisher: str | Publisher | None = None,
        temporary: bool = False,
        skip_req_missing: bool = False,
    ) -> Subscriber: ...

    @overload
    def register(
        self,
        *,
        events: type | tuple[type, ...] | None = None,
        priority: int = 16,
        providers: Sequence[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
        publisher: str | Publisher | None = None,
        temporary: bool = False,
        skip_req_missing: bool = False,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    def register(
        self,
        func: Callable[..., Any] | None = None,
        events: type | tuple[type, ...] | None = None,
        *,
        priority: int = 16,
        providers: Sequence[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
        publisher: str | Publisher | None = None,
        temporary: bool = False,
        skip_req_missing: bool = False,
    ):
        """注册一个订阅者"""
        providers = providers or []
        if isinstance(publisher, Publisher):
            pubs = [publisher]
        elif isinstance(publisher, str) and publisher in _publishers:
            pubs = [_publishers[publisher]]
        elif not events:
            pubs = [_backend_publisher]
        else:
            pubs = [
                *filter(
                    None, (filter_publisher(target) for target in (events if isinstance(events, tuple) else (events,)))
                )
            ]
            if not pubs:
                pubs = [Publisher(target) for target in (events if isinstance(events, tuple) else (events,))]
        pub_providers = [p for pub in pubs for p in pub.providers]

        def register_wrapper(exec_target: Callable, /) -> Subscriber:
            _providers = [
                *global_providers,
                *pub_providers,
                *self.providers,
                *providers,
            ]
            res = Subscriber(
                exec_target,
                priority=priority,
                providers=_providers,
                dispose=self.remove_subscriber,
                temporary=temporary,
                skip_req_missing=skip_req_missing,
            )
            res.propagates(*self.propagators)
            self.subscribers[res.id] = (res, {pub.id for pub in pubs})
            return res

        if func:
            return register_wrapper(func)
        return register_wrapper

    def get_subscribers(self, publisher_id: str, pass_backend: bool = True) -> list[Subscriber]:
        return [
            slot[0] for slot in self.subscribers.values()
            if publisher_id in slot[1] or (pass_backend and _backend_publisher.id in slot[1])
        ]

    def iter_subscribers(self, publisher_id: str, pass_backend: bool = True):
        for slot in self.subscribers.values():
            if publisher_id in slot[1] or (pass_backend and _backend_publisher.id in slot[1]):
                yield slot[0]

    def dispose(self):
        self.available = False
        self.subscribers.clear()
        _scopes.pop(self.id, None)
