from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from secrets import token_urlsafe
from typing import Any, Callable, TypeVar, overload

from .context import scope_ctx
from .handler import dispatch
from .provider import Provider, ProviderFactory, global_providers, get_providers
from .publisher import Publisher, _publishers, filter_publisher, search_publisher
from .subscriber import Propagator, Subscriber
from .typing import Result, Resultable

T = TypeVar("T")

_scopes: dict[str, Scope] = {}


class Scope:
    def __init__(self, id_: str | None = None):
        self.id = id_ or token_urlsafe(16)
        self.subscribers: dict[str, tuple[Subscriber, str]] = {}
        self.available = True
        self.providers: list[Provider[Any] | ProviderFactory] = []
        self.propagators: list[Propagator] = []

    def __repr__(self):
        return f"{self.__class__.__name__}::{self.id}"

    async def emit(self, event: Any) -> None:
        """主动向自己的订阅者发布事件"""
        await dispatch(self.iter_subscribers(search_publisher(event)), event)

    @overload
    async def bail(self, event: Resultable[T]) -> Result[T] | None: ...

    @overload
    async def bail(self, event: Any) -> Result[Any] | None: ...

    async def bail(self, event: Any) -> Result | None:
        """主动向自己的订阅者发布事件, 并返回结果"""
        return await dispatch(self.iter_subscribers(search_publisher(event)), event, return_result=True)

    def bind(self, *args: Provider | type[Provider] | ProviderFactory | type[ProviderFactory]) -> None:
        """增加间接 Provider"""
        self.providers.extend(p() if isinstance(p, type) else p for p in args)

    def unbind(
        self,
        arg: Provider | type[Provider] | ProviderFactory | type[ProviderFactory],
    ) -> None:
        """移除间接 Provider"""
        idx = [i for i, p in enumerate(self.providers) if (isinstance(arg, (ProviderFactory, Provider)) and p == arg) or (isinstance(arg, type) and isinstance(p, arg))]
        for i in reversed(idx):
            self.providers.pop(i)

    @contextmanager
    def context(self):
        token = scope_ctx.set(self)
        try:
            yield self
        finally:
            scope_ctx.reset(token)

    def remove_subscriber(self, subscriber: Subscriber) -> None:
        """移除订阅者"""
        self.subscribers.pop(subscriber.id, None)

    @overload
    def register(
        self,
        func: Callable[..., Any],
        event: type | None = None,
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
        event: type | None = None,
        priority: int = 16,
        providers: Sequence[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
        publisher: str | Publisher | None = None,
        temporary: bool = False,
        skip_req_missing: bool = False,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    def register(
        self,
        func: Callable[..., Any] | None = None,
        event: type | None = None,
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
            pub_id = publisher.id
        elif isinstance(publisher, str) and publisher in _publishers:
            pub_id = publisher
        elif not event:
            pub_id = "$backend"
        else:
            pub_id = (filter_publisher(event) or Publisher(event)).id

        def register_wrapper(exec_target: Callable, /) -> Subscriber:
            _providers = [*global_providers, *(get_providers(event) if event else ()), *self.providers, *providers]
            res = Subscriber(
                exec_target,
                priority=priority,
                providers=_providers,
                dispose=self.remove_subscriber,
                temporary=temporary,
                skip_req_missing=skip_req_missing,
            )
            res.propagates(*self.propagators)
            self.subscribers[res.id] = (res, pub_id)
            return res

        if func:
            return register_wrapper(func)
        return register_wrapper

    def get_subscribers(self, publisher: Publisher | None, pass_backend: bool = True) -> list[Subscriber]:
        pub_id = publisher.id if publisher else "$backend" if pass_backend else None
        return [slot[0] for slot in self.subscribers.values() if pub_id and slot[1] == pub_id]

    def iter_subscribers(self, publisher: Publisher | None, pass_backend: bool = True):
        pub_id = publisher.id if publisher else "$backend" if pass_backend else None
        for slot in self.subscribers.values():
            if pub_id and slot[1] == pub_id:
                yield slot[0]

    def dispose(self):
        self.available = False
        self.subscribers.clear()
        _scopes.pop(self.id, None)
