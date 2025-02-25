from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping, Sequence
from itertools import chain
from typing import Any, Callable, TypeVar, overload
from weakref import finalize

from .context import scope_ctx
from .event import BaseEvent
from .handler import dispatch
from .provider import Provider, ProviderFactory
from .publisher import ExternalPublisher, Publisher, _publishers, search_publisher
from .scope import Scope, _scopes
from .subscriber import Subscriber
from .typing import Contexts, Result, Resultable

T = TypeVar("T")


class EventSystem:
    _ref_tasks = set()
    _global_scope = Scope("$global")
    external_gathers: dict[type, Callable[[Any], Awaitable[Contexts]]]

    def __init__(self):
        self.loop: asyncio.AbstractEventLoop | None = None
        _scopes["$global"] = self._global_scope
        self.external_gathers = {}
        self.global_skip_req_missing = False

        def _remove(es):
            for task in es._ref_tasks:
                if not task.done():
                    task.cancel()
            es._ref_tasks.clear()

        finalize(self, _remove, self)

    async def setup_fetch(self):
        self._ref_tasks.add(asyncio.create_task(self._loop_fetch()))

    async def _loop_fetch(self):
        while True:
            for publisher in _publishers.values():
                if not (event := (await publisher.supply())):
                    continue
                self.post(event)
            await asyncio.sleep(0.05)

    def scope(self, id_: str | None = None):
        sp = Scope(id_)
        _scopes[sp.id] = sp
        return sp

    def define(
        self,
        target: type[T],
        name: str | None = None,
        supplier: Callable[[T], Mapping[str, Any]] | None = None,
    ) -> Publisher:
        if name and name in _publishers:
            return _publishers[name]
        if hasattr(target, "__publisher__"):
            _id = target.__publisher__  # type: ignore
        else:
            _id = f"$event:{target.__name__}"
        if _id in _publishers:
            return _publishers[_id]
        if issubclass(target, BaseEvent):
            publisher = Publisher(target, name)
        else:
            publisher = ExternalPublisher(target, name, supplier)
            self.external_gathers[target] = publisher.external_gather
        return publisher

    def publish(self, event: Any, scope: str | Scope | None = None, inherit_ctx: Contexts | None = None):
        """发布事件"""
        loop = self.loop or asyncio.get_running_loop()
        pub_id = search_publisher(event).id
        if isinstance(scope, str) and ((sp := _scopes.get(scope)) and sp.available):
            task = loop.create_task(
                dispatch(
                    sp.iter_subscribers(pub_id),
                    event,
                    external_gather=self.external_gathers.get(event.__class__, None),
                    inherit_ctx=inherit_ctx,
                )
            )
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        if isinstance(scope, Scope) and scope.available:
            task = loop.create_task(
                dispatch(
                    scope.iter_subscribers(pub_id),
                    event,
                    external_gather=self.external_gathers.get(event.__class__, None),
                    inherit_ctx=inherit_ctx,
                )
            )
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        scopes = [sp for sp in _scopes.values() if sp.available]
        task = loop.create_task(
            dispatch(
                chain.from_iterable(sp.iter_subscribers(pub_id) for sp in scopes),
                event,
                external_gather=self.external_gathers.get(event.__class__, None),
                inherit_ctx=inherit_ctx,
            )
        )
        self._ref_tasks.add(task)
        task.add_done_callback(self._ref_tasks.discard)
        return task

    @overload
    def post(self, event: Resultable[T], scope: str | Scope | None = None) -> asyncio.Task[Result[T] | None]: ...

    @overload
    def post(self, event: Any, scope: str | Scope | None = None) -> asyncio.Task[Result[Any] | None]: ...

    def post(self, event: Any, scope: str | Scope | None = None):
        """发布事件并返回第一个响应结果"""
        loop = self.loop or asyncio.get_running_loop()
        pub_id = search_publisher(event).id
        if isinstance(scope, str) and ((sp := _scopes.get(scope)) and sp.available):
            task = loop.create_task(
                dispatch(
                    sp.iter_subscribers(pub_id),
                    event,
                    return_result=True,
                    external_gather=self.external_gathers.get(event.__class__, None),
                )
            )
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        if isinstance(scope, Scope) and scope.available:
            task = loop.create_task(
                dispatch(
                    scope.iter_subscribers(pub_id),
                    event,
                    return_result=True,
                    external_gather=self.external_gathers.get(event.__class__, None),
                )
            )
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        task = loop.create_task(
            dispatch(
                chain.from_iterable(sp.iter_subscribers(pub_id) for sp in _scopes.values() if sp.available),
                event,
                return_result=True,
                external_gather=self.external_gathers.get(event.__class__, None),
            )
        )
        self._ref_tasks.add(task)
        task.add_done_callback(self._ref_tasks.discard)
        return task

    @overload
    def on(
        self,
        events: type | tuple[type, ...],
        func: Callable[..., Any],
        *,
        priority: int = 16,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
        skip_req_missing: bool | None = None,
    ) -> Subscriber: ...

    @overload
    def on(
        self,
        events: type | tuple[type, ...],
        *,
        priority: int = 16,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
        skip_req_missing: bool | None = None,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    @overload
    def on(
        self,
        *,
        priority: int = 16,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
        skip_req_missing: bool | None = None,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    def on(
        self,
        events: type | tuple[type, ...] | None = None,
        func: Callable[..., Any] | None = None,
        priority: int = 16,
        providers: Sequence[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
        temporary: bool = False,
        skip_req_missing: bool | None = None,
    ):
        _skip_req_missing = self.global_skip_req_missing if skip_req_missing is None else skip_req_missing
        if events:
            for target in events if isinstance(events, tuple) else (events,):
                self.define(target)
        if not (scope := scope_ctx.get()):
            scope = self._global_scope
        if not func:
            return scope.register(events=events, priority=priority, providers=providers, skip_req_missing=_skip_req_missing, temporary=temporary)
        return scope.register(func, events=events, priority=priority, providers=providers, skip_req_missing=_skip_req_missing, temporary=temporary)

    @overload
    def use(
        self,
        pub: str | Publisher,
        func: Callable[..., Any],
        *,
        priority: int = 16,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
        skip_req_missing: bool | None = None,
    ) -> Subscriber: ...

    @overload
    def use(
        self,
        pub: str | Publisher,
        *,
        priority: int = 16,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
        skip_req_missing: bool | None = None,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    def use(
        self,
        pub: str | Publisher,
        func: Callable[..., Any] | None = None,
        priority: int = 16,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
        skip_req_missing: bool | None = None,
    ):
        _skip_req_missing = self.global_skip_req_missing if skip_req_missing is None else skip_req_missing
        if not (scope := scope_ctx.get()):
            scope = self._global_scope
        if not func:
            return scope.register(priority=priority, providers=providers, temporary=temporary, skip_req_missing=_skip_req_missing, publisher=pub)
        return scope.register(func, priority=priority, providers=providers, temporary=temporary, skip_req_missing=_skip_req_missing, publisher=pub)


es = EventSystem()


C = TypeVar("C")


@overload
def make_event(cls: type[C]) -> type[C]: ...


@overload
def make_event(*, name: str) -> Callable[[type[C]], type[C]]: ...


def make_event(cls: type[C] | None = None, *, name: str | None = None):

    def wrapper(_cls: type[C], /):
        if not hasattr(_cls, "gather"):
            annotation = getattr(_cls, "__annotations__", {})

            async def _gather(self, context: Contexts):
                for key in annotation:
                    if key in ("providers", "auxiliaries"):
                        continue
                    context[key] = getattr(self, key, None)

            _cls.gather = _gather  # type: ignore

        _cls.__publisher__ = es.define(_cls, name).id  # type: ignore
        return _cls  # type: ignore

    if cls:
        return wrapper(cls)
    return wrapper
