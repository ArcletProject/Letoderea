from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from secrets import token_urlsafe
from typing import Any, TypeVar, Generic
from collections.abc import Callable, Awaitable

from tarina import ContextModel

from .provider import TProviders, Provider, ProviderFactory, global_providers
from .publisher import Publisher, _publishers, filter_publisher
from .subscriber import Propagator, Subscriber
from .decorate import Check, enter_if, bypass_if

T = TypeVar("T")
TC = TypeVar("TC")

_scopes: dict[str, Scope] = {}


scope_ctx: ContextModel[Scope] = ContextModel("scope_ctx")
global_propagators: list[Propagator] = []


@dataclass
class RegisterWrapper(Generic[T, TC]):
    _scope: Scope
    _event: type | None
    _priority: int
    _providers: TProviders
    _propagators: list[Propagator]
    _publisher: Publisher | None
    _pub_id: str
    _once: bool
    _skip_req_missing: bool

    def if_(self, predicate: Check | Callable[..., bool] | Callable[..., Awaitable[bool]] | bool, priority: int = 0):
        self._propagators.append(enter_if(predicate) / priority)
        return self

    def unless(self, predicate: Check | Callable[..., bool] | Callable[..., Awaitable[bool]] | bool, priority: int = 0):
        self._propagators.append(bypass_if(predicate) / priority)
        return self

    def propagate(self, *propagators: Propagator):
        self._propagators.extend(propagators)
        return self

    def __call__(self, func: Callable, /) -> Subscriber[T]:
        if isinstance(func, Subscriber):
            func = func.callable_target
        res = Subscriber(func, priority=self._priority, providers=self._providers, dispose=self._scope.remove_subscriber, once=self._once, skip_req_missing=self._skip_req_missing, _listen=self._event)
        res.propagates(*self._propagators)
        if not self._publisher or (self._publisher and self._publisher.check_subscriber(res)):
            self._scope.subscribers[res.id] = (res, self._pub_id)
        return res


class Scope:
    global_skip_req_missing = False
    __wrapper_class__ = RegisterWrapper

    @classmethod
    def of(cls, id_: str | None = None):
        sp = cls(id_)
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

    def register(self, func: Callable[..., Any] | None = None, event: type | None = None, *, priority: int = 16, providers: TProviders | None = None, propagators: list[Propagator] | None = None, publisher: str | Publisher | None = None, once: bool = False, skip_req_missing: bool | None = None):
        """注册一个订阅者"""
        _skip_req_missing = self.global_skip_req_missing if skip_req_missing is None else skip_req_missing
        providers = providers or []
        propagators = propagators or []
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

        register_wrapper = self.__wrapper_class__(self, _listen, priority, [*global_providers, *event_providers, *self.providers, *providers], [*global_propagators, *self.propagators, *propagators], _pub, pub_id, once, _skip_req_missing)
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


def on(event: type, func: Callable[..., Any] | None = None, priority: int = 16, providers: TProviders | None = None, propagators: list[Propagator] | None = None, once: bool = False, skip_req_missing: bool | None = None):
    if not (scope := scope_ctx.get()):
        scope = _scopes["$global"]
    if not func:
        return scope.register(event=event, priority=priority, providers=providers, propagators=propagators, skip_req_missing=skip_req_missing, once=once)
    return scope.register(func, event=event, priority=priority, providers=providers, propagators=propagators, skip_req_missing=skip_req_missing, once=once)


def on_global(func: Callable[..., Any] | None = None, priority: int = 16, once: bool = False, skip_req_missing: bool | None = None):
    if not (scope := scope_ctx.get()):
        scope = _scopes["$global"]
    if not func:
        return scope.register(event=None, priority=priority, skip_req_missing=skip_req_missing, once=once)
    return scope.register(func, event=None, priority=priority, skip_req_missing=skip_req_missing, once=once)


def use(pub: str | Publisher, func: Callable[..., Any] | None = None, priority: int = 16, providers: TProviders | None = None, propagators: list[Propagator] | None = None, once: bool = False, skip_req_missing: bool | None = None):
    if not (scope := scope_ctx.get()):
        scope = _scopes["$global"]
    if not func:
        return scope.register(priority=priority, providers=providers, propagators=propagators, once=once, skip_req_missing=skip_req_missing, publisher=pub)
    return scope.register(func, priority=priority, providers=providers, propagators=propagators, once=once, skip_req_missing=skip_req_missing, publisher=pub)
