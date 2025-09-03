from __future__ import annotations

from contextlib import contextmanager
from secrets import token_urlsafe
from typing import Any, TypeVar
from collections.abc import Callable

from tarina import ContextModel

from .provider import TProviders, Provider, ProviderFactory, global_providers
from .publisher import Publisher, _publishers, filter_publisher
from .subscriber import Propagator, Subscriber

T = TypeVar("T")

_scopes: dict[str, Scope] = {}


scope_ctx: ContextModel[Scope] = ContextModel("scope_ctx")
global_propagators: list[Propagator] = []


class Scope:
    global_skip_req_missing = False

    @staticmethod
    def of(id_: str | None = None):
        sp = Scope(id_)
        _scopes[sp.id] = sp
        return sp

    def __init__(self, id_: str | None = None):
        self.id = id_ or token_urlsafe(16)
        self.subscribers = {}
        self.available = True
        self.providers = []
        self.propagators = []

    def __repr__(self):
        return f"{self.__class__.__name__}::{self.id}"

    def bind(self, *args: Provider | type[Provider] | ProviderFactory | type[ProviderFactory]) -> None:
        """增加间接 Provider"""
        self.providers.extend(p() if isinstance(p, type) else p for p in args)

    def unbind(self, arg: Provider | type[Provider] | ProviderFactory | type[ProviderFactory]) -> None:  # pragma: no cover
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

    def register(self, func: Callable[..., Any] | None = None, event: type | None = None, *, priority: int = 16, providers: TProviders | None = None, publisher: str | Publisher | None = None, once: bool = False, skip_req_missing: bool | None = None):
        """注册一个订阅者"""
        _skip_req_missing = self.global_skip_req_missing if skip_req_missing is None else skip_req_missing
        providers = providers or []
        if isinstance(publisher, Publisher):
            pub_id = publisher.id
            event_providers = publisher.providers
            _listen = publisher.target
            _pub = publisher
        elif isinstance(publisher, str) and publisher in _publishers:
            pub_id = publisher
            _pub = _publishers[publisher]
            event_providers = _pub.providers
            _listen = _pub.target
        elif not event:
            pub_id = "$backend"
            event_providers = []
            _listen = _pub = None
        else:
            _pub = (filter_publisher(event) or Publisher(event))
            pub_id = _pub.id
            event_providers = _pub.providers
            _listen = event

        def register_wrapper(exec_target: Callable, /) -> Subscriber:
            if isinstance(exec_target, Subscriber):
                exec_target = exec_target.callable_target
            _providers = [*global_providers, *event_providers, *self.providers, *providers]
            res = Subscriber(
                exec_target,
                priority=priority,
                providers=_providers,
                dispose=self.remove_subscriber,
                once=once,
                skip_req_missing=_skip_req_missing,
                _listen=_listen,
            )
            res.propagates(*global_propagators, *self.propagators)
            if not _pub or (_pub and _pub.check_subscriber(res)):
                self.subscribers[res.id] = (res, pub_id)
            return res

        if func:
            return register_wrapper(func)
        return register_wrapper

    def iter(self, pub_ids: set[str], pass_backend: bool = True):
        for slot in self.subscribers.values():
            if slot[1] in pub_ids or (pass_backend and slot[1] == "$backend"):
                yield slot[0]

    def disable(self):
        self.available = False
        for subscriber in self.subscribers.values():
            subscriber[0].available = False

    def enable(self):
        self.available = True
        for subscriber in self.subscribers.values():
            subscriber[0].available = True

    def dispose(self):
        self.disable()
        while self.subscribers:
            _, (sub, __) = self.subscribers.popitem()
            sub.dispose()
        _scopes.pop(self.id, None)


_scopes["$global"] = Scope("$global")


def configure(skip_req_missing: bool = False):
    global global_skip_req_missing
    global_skip_req_missing = skip_req_missing


def on(event: type, func: Callable[..., Any] | None = None, priority: int = 16, providers: TProviders | None = None, once: bool = False, skip_req_missing: bool | None = None):
    if not (scope := scope_ctx.get()):
        scope = _scopes["$global"]
    if not func:
        return scope.register(event=event, priority=priority, providers=providers, skip_req_missing=skip_req_missing, once=once)
    return scope.register(func, event=event, priority=priority, providers=providers, skip_req_missing=skip_req_missing, once=once)


def on_global(func: Callable[..., Any] | None = None, priority: int = 16, once: bool = False, skip_req_missing: bool | None = None):
    if not (scope := scope_ctx.get()):
        scope = _scopes["$global"]
    if not func:
        return scope.register(event=None, priority=priority, skip_req_missing=skip_req_missing, once=once)
    return scope.register(func, event=None, priority=priority, skip_req_missing=skip_req_missing, once=once)


def use(pub: str | Publisher, func: Callable[..., Any] | None = None, priority: int = 16, providers: TProviders | None = None, once: bool = False, skip_req_missing: bool | None = None):
    if not (scope := scope_ctx.get()):
        scope = _scopes["$global"]
    if not func:
        return scope.register(priority=priority, providers=providers, once=once, skip_req_missing=skip_req_missing, publisher=pub)
    return scope.register(func, priority=priority, providers=providers, once=once, skip_req_missing=skip_req_missing, publisher=pub)
