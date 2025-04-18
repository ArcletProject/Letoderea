from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from secrets import token_urlsafe
from typing import Any, Callable, ClassVar, TypeVar, overload

from tarina import ContextModel

from .provider import TProviders, Provider, ProviderFactory, global_providers
from .publisher import Publisher, _publishers, filter_publisher
from .subscriber import Propagator, Subscriber

T = TypeVar("T")

_scopes: dict[str, Scope] = {}


scope_ctx: ContextModel["Scope"] = ContextModel("scope_ctx")


class Scope:
    global_skip_req_missing: ClassVar[bool] = False

    @staticmethod
    def of(id_: str | None = None):
        sp = Scope(id_)
        _scopes[sp.id] = sp
        return sp

    def __init__(self, id_: str | None = None):
        self.id = id_ or token_urlsafe(16)
        self.subscribers: dict[str, tuple[Subscriber, str]] = {}
        self.available = True
        self.providers: list[Provider[Any] | ProviderFactory] = []
        self.propagators: list[Propagator] = []

    def __repr__(self):
        return f"{self.__class__.__name__}::{self.id}"

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
    def register(self, func: Callable[..., Any], event: type | None = None, *, priority: int = 16, providers: TProviders | None = None, publisher: str | Publisher | None = None, once: bool = False, skip_req_missing: bool | None = None) -> Subscriber: ...

    @overload
    def register(self, *, event: type | None = None, priority: int = 16, providers: TProviders | None = None, publisher: str | Publisher | None = None, once: bool = False, skip_req_missing: bool | None = None) -> Callable[[Callable[..., Any]], Subscriber]: ...

    def register(self, func: Callable[..., Any] | None = None, event: type | None = None, *, priority: int = 16, providers: TProviders | None = None, publisher: str | Publisher | None = None, once: bool = False, skip_req_missing: bool | None = None):
        """注册一个订阅者"""
        _skip_req_missing = self.global_skip_req_missing if skip_req_missing is None else skip_req_missing
        providers = providers or []
        if isinstance(publisher, Publisher):
            pub_id = publisher.id
            event_providers = publisher.providers
        elif isinstance(publisher, str) and publisher in _publishers:
            pub_id = publisher
            event_providers = _publishers[publisher].providers
        elif not event:
            pub_id = "$backend"
            event_providers = []
        else:
            pub = (filter_publisher(event) or Publisher(event))
            pub_id = pub.id
            event_providers = pub.providers

        def register_wrapper(exec_target: Callable, /) -> Subscriber:
            _providers = [*global_providers, *event_providers, *self.providers, *providers]
            res = Subscriber(
                exec_target,
                priority=priority,
                providers=_providers,
                dispose=self.remove_subscriber,
                once=once,
                skip_req_missing=_skip_req_missing,
            )
            res.propagates(*self.propagators)
            self.subscribers[res.id] = (res, pub_id)
            return res

        if func:
            return register_wrapper(func)
        return register_wrapper

    def iter(self, pub_ids: set[str], pass_backend: bool = True):
        for slot in self.subscribers.values():
            if slot[1] in pub_ids or (pass_backend and slot[1] == "$backend"):
                yield slot[0]

    def dispose(self):
        self.available = False
        self.subscribers.clear()
        _scopes.pop(self.id, None)


_scopes["$global"] = Scope("$global")


def configure(skip_req_missing: bool = False):
    global global_skip_req_missing
    global_skip_req_missing = skip_req_missing


@overload
def on(event: type, func: Callable[..., Any], *, priority: int = 16, providers: TProviders | None = None, once: bool = False, skip_req_missing: bool | None = None) -> Subscriber: ...


@overload
def on(event: type, *, priority: int = 16, providers: TProviders | None = None, once: bool = False, skip_req_missing: bool | None = None) -> Callable[[Callable[..., Any]], Subscriber]: ...


@overload
def on(*, priority: int = 16, providers: TProviders | None = None, once: bool = False, skip_req_missing: bool | None = None) -> Callable[[Callable[..., Any]], Subscriber]: ...


def on(event: type | None = None, func: Callable[..., Any] | None = None, priority: int = 16, providers: TProviders | None = None, once: bool = False, skip_req_missing: bool | None = None):
    if not (scope := scope_ctx.get()):
        scope = _scopes["$global"]
    if not func:
        return scope.register(event=event, priority=priority, providers=providers, skip_req_missing=skip_req_missing, once=once)
    return scope.register(func, event=event, priority=priority, providers=providers, skip_req_missing=skip_req_missing, once=once)


@overload
def on_global(func: Callable[..., Any], *, priority: int = 16, once: bool = False, skip_req_missing: bool | None = None) -> Subscriber: ...


@overload
def on_global(*, priority: int = 16, once: bool = False, skip_req_missing: bool | None = None) -> Callable[[Callable[..., Any]], Subscriber]: ...


def on_global(func: Callable[..., Any] | None = None, priority: int = 16, once: bool = False, skip_req_missing: bool | None = None):
    if not (scope := scope_ctx.get()):
        scope = _scopes["$global"]
    if not func:
        return scope.register(event=None, priority=priority, skip_req_missing=skip_req_missing, once=once)
    return scope.register(func, event=None, priority=priority, skip_req_missing=skip_req_missing, once=once)


@overload
def use(pub: str | Publisher, func: Callable[..., Any], *, priority: int = 16, providers: TProviders | None = None, once: bool = False, skip_req_missing: bool | None = None) -> Subscriber: ...


@overload
def use(pub: str | Publisher, *, priority: int = 16, providers: TProviders | None = None, once: bool = False, skip_req_missing: bool | None = None) -> Callable[[Callable[..., Any]], Subscriber]: ...


def use(pub: str | Publisher, func: Callable[..., Any] | None = None, priority: int = 16, providers: TProviders | None = None, once: bool = False, skip_req_missing: bool | None = None):
    if not (scope := scope_ctx.get()):
        scope = _scopes["$global"]
    if not func:
        return scope.register(priority=priority, providers=providers, once=once, skip_req_missing=skip_req_missing, publisher=pub)
    return scope.register(func, priority=priority, providers=providers, once=once, skip_req_missing=skip_req_missing, publisher=pub)
