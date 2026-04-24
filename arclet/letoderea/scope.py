from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from dataclasses import dataclass
from fnmatch import filter as fnfilter
from secrets import token_urlsafe
from typing import Any, Generic, TypeVar

from tarina import ContextModel

from .decorate import Check, bypass_if, enter_if
from .provider import Provider, ProviderFactory, TProviders, global_providers
from .effect import EffectManager
from .publisher import Publisher, _publishers, filter_publisher
from .subscriber import Propagator, Subscriber

T = TypeVar("T")
TC = TypeVar("TC")

_scopes: dict[str, Scope] = {}


scope_ctx: ContextModel[Scope] = ContextModel("scope_ctx")
global_propagators: list[Propagator] = []


@dataclass(slots=True, frozen=True)
class SubscriberSlot:
    subscriber: Subscriber
    publisher_id: str
    priority: int


@dataclass
class RegisterWrapper(Generic[T, TC]):
    _scope: Scope
    _publisher: tuple[type, Publisher] | tuple[tuple[type, ...], tuple[Publisher, ...]] | None
    _priority: int
    _providers: TProviders
    _propagators: list[Propagator]
    _effect_manager: EffectManager
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
        events = self._publisher[0] if self._publisher else None
        res = Subscriber(func, priority=self._priority, providers=self._providers, dispose=self._scope.remove_subscriber, once=self._once, skip_req_missing=self._skip_req_missing, _listen=events)
        for pro in self._propagators:
            res.propagate(pro, _skip_providers=True)
        pubs = self._publisher[1] if self._publisher else None
        pubs = (pubs,) if isinstance(pubs, Publisher) else pubs
        if not pubs:
            self._scope.subscribers.append(SubscriberSlot(res, "$backend", res.priority))
        else:
            for pub in pubs:
                if pub.check_subscriber(res):
                    self._scope.subscribers.append(SubscriberSlot(res, pub.id, res.priority))
        self._effect_manager.effect(lambda: res.dispose, res.id)
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
        self.subscribers: list[SubscriberSlot] = []
        self._effect_manager = EffectManager()
        self.effect = self._effect_manager.effect
        self.available = True
        self.providers = []
        self.propagators = []

    def __repr__(self):
        return f"{self.__class__.__name__}::{self.id}"

    @contextmanager
    def context(self):
        token = scope_ctx.set(self)
        try:
            yield self
        finally:
            scope_ctx.reset(token)

    def remove_subscriber(self, subscriber: Subscriber) -> None:
        """移除订阅者"""
        indexes = [i for i, slot in enumerate(self.subscribers) if slot.subscriber.id == subscriber.id]
        for i in reversed(indexes):
            self.subscribers.pop(i)

    def register(self, func: Callable[..., Any] | None = None, event: type | None = None, *, priority: int = 16, providers: TProviders | None = None, propagators: list[Propagator] | None = None, publisher: str | Publisher | None = None, once: bool = False, skip_req_missing: bool | None = None):
        """注册一个订阅者"""
        _skip_req_missing = self.global_skip_req_missing if skip_req_missing is None else skip_req_missing
        providers = providers or []
        propagators = propagators or []
        if isinstance(publisher, Publisher):
            event_providers = publisher.providers
            slots = (publisher.target, publisher)
        elif isinstance(publisher, str):
            if publisher in _publishers:
                _pub = _publishers[publisher]
                event_providers = _pub.providers
                slots = (_pub.target, _pub)
            elif not (pub_ids := tuple(p for p in fnfilter(_publishers.keys(), publisher))):
                slots = None
                event_providers = []
            else:
                pubs = tuple(_publishers[pub_id] for pub_id in pub_ids)
                event_providers = [p for pub in pubs for p in pub.providers]
                slots = (tuple(pub.target for pub in pubs), pubs)
        elif not event:
            slots = None
            event_providers = []
        else:
            _pub = (filter_publisher(event) or Publisher(event))
            event_providers = _pub.providers
            slots = (event, _pub)

        _propagators: list[Propagator] = [*global_propagators, *self.propagators, *propagators]
        _propagator_providers = [p for pro in _propagators for p in pro.providers()]
        register_wrapper = self.__wrapper_class__(self, slots, priority, [*global_providers, *event_providers, *self.providers, *providers, *_propagator_providers], _propagators, self._effect_manager, once, _skip_req_missing)
        if func:
            return register_wrapper(func)
        return register_wrapper

    def iter(self, pub_ids: set[str], pass_backend: bool = True):
        for slot in self.subscribers:
            if slot.publisher_id in pub_ids or (pass_backend and slot.publisher_id == "$backend"):
                yield slot.subscriber

    def disable(self):
        self.available = False
        for slot in self.subscribers:
            slot.subscriber.available = False

    def enable(self):
        self.available = True
        for slot in self.subscribers:
            slot.subscriber.available = True

    def dispose(self):
        self.disable()
        _scopes.pop(self.id, None)
        return self._effect_manager.dispose()


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
