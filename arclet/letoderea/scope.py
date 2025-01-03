from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager, suppress
from secrets import token_urlsafe
from typing import Any, Callable, TypeVar, overload

from .auxiliary import BaseAuxiliary, global_auxiliaries
from .context import scope_ctx
from .handler import dispatch
from .provider import Provider, ProviderFactory, global_providers
from .publisher import Publisher, _backend_publisher, _publishers, filter_publisher, search_publisher
from .subscriber import Subscriber
from .typing import Result, Resultable

T = TypeVar("T")

_scopes: dict[str, Scope] = {}


class Scope:
    id: str
    subscribers: dict[str, tuple[Subscriber, set[str]]]
    providers: list[Provider[Any] | ProviderFactory]
    auxiliaries: list[BaseAuxiliary]

    def __init__(
        self,
        id_: str | None = None,
    ):
        self.id = id_ or token_urlsafe(16)
        self.subscribers = {}
        self.available = True
        self.providers = []
        self.auxiliaries = []

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
        *args: BaseAuxiliary | Provider | type[Provider] | ProviderFactory | type[ProviderFactory],
    ) -> None:
        """为发布器增加间接 Provider 或 Auxiliaries"""
        self.auxiliaries.extend(a for a in args if isinstance(a, BaseAuxiliary))
        providers = [p for p in args if not isinstance(p, BaseAuxiliary)]
        self.providers.extend(p() if isinstance(p, type) else p for p in providers)

    def unbind(
        self,
        arg: Provider | BaseAuxiliary | type[Provider] | ProviderFactory | type[ProviderFactory],
    ) -> None:
        """移除发布器的间接 Provider 或 Auxiliaries"""
        if isinstance(arg, BaseAuxiliary):
            with suppress(ValueError):
                self.auxiliaries.remove(arg)
        elif isinstance(arg, (ProviderFactory, Provider)):
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
            pubs = [
                *filter(
                    None, (filter_publisher(target) for target in (events if isinstance(events, tuple) else (events,)))
                )
            ]
            if not pubs:
                pubs = [Publisher(target) for target in (events if isinstance(events, tuple) else (events,))]
        pub_providers = [p for pub in pubs for p in pub.providers]
        pub_auxiliaries = [a for pub in pubs for a in pub.auxiliaries]

        def register_wrapper(exec_target: Callable, /) -> Subscriber:
            _providers = [
                *global_providers,
                *pub_providers,
                *self.providers,
                *providers,
            ]
            _auxiliaries = [
                *global_auxiliaries,
                *pub_auxiliaries,
                *self.auxiliaries,
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
            self.subscribers[res.id] = (res, {pub.id for pub in pubs})
            return res

        if func:
            return register_wrapper(func)
        return register_wrapper

    def get_subscribers(self, publisher_id: str) -> list[Subscriber]:
        return [
            slot[0] for slot in self.subscribers.values() if publisher_id in slot[1] or _backend_publisher.id in slot[1]
        ]

    def iter_subscribers(self, publisher_id: str):
        for slot in self.subscribers.values():
            if publisher_id in slot[1] or _backend_publisher.id in slot[1]:
                yield slot[0]

    def dispose(self):
        self.available = False
        self.subscribers.clear()
        _scopes.pop(self.id, None)
