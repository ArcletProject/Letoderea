from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from itertools import chain
from typing import Any, Awaitable, Callable, TypeVar, overload
from weakref import finalize

from .auxiliary import BaseAuxiliary
from .context import publisher_ctx
from .event import BaseEvent
from .handler import dispatch
from .provider import Provider, ProviderFactory
from .publisher import BackendPublisher, ExternalPublisher, Publisher
from .subscriber import Subscriber
from .typing import Contexts, Result, Resultable

T = TypeVar("T")


class EventSystem:
    _ref_tasks = set()
    _backend_publisher: Publisher = BackendPublisher("__backend__publisher__")
    publishers: dict[str, Publisher]
    external_gathers: dict[type, Callable[[Any], Awaitable[Contexts]]]

    def __init__(self):
        self.publishers = {}
        self.external_gathers = {}

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
            for publisher in self.publishers.values():
                if not (event := (await publisher.supply())):
                    continue
                self.post(event, publisher)
            await asyncio.sleep(0.05)

    def register(self, *publishers: Publisher):
        """注册发布者"""
        for publisher in publishers:
            self.publishers[publisher.id] = publisher

    def define(
        self,
        name: str,
        target: type[T] | None = None,
        supplier: Callable[[T], Mapping[str, Any]] | None = None,
        predicate: Callable[[T], bool] | None = None,
    ) -> Publisher:
        if name in self.publishers:
            return self.publishers[name]
        elif predicate and (_key := f"{name}::{predicate}") in self.publishers:
            return self.publishers[_key]
        if not target:
            if not predicate:
                raise ValueError("If target is not provided, predicate must be provided")
            publisher = BackendPublisher(name, predicate)
        elif issubclass(target, BaseEvent):
            publisher = Publisher(name, target, predicate=predicate)
        else:
            publisher = ExternalPublisher(name, target, supplier, predicate)
            self.external_gathers[target] = publisher.external_gather
        self.register(publisher)
        return publisher

    def publish(self, event: Any, publisher: str | Publisher | None = None):
        """发布事件"""
        loop = asyncio.get_running_loop()
        if isinstance(publisher, str) and (pub := self.publishers.get(publisher)):
            task = loop.create_task(
                dispatch(
                    pub.subscribers.values(), event, external_gather=self.external_gathers.get(event.__class__, None)
                )
            )
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        if isinstance(publisher, Publisher):
            task = loop.create_task(
                dispatch(
                    publisher.subscribers.values(),
                    event,
                    external_gather=self.external_gathers.get(event.__class__, None),
                )
            )
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        if hasattr(event, "__publisher__") and (pub := self.publishers.get(event.__publisher__)):
            task = loop.create_task(
                dispatch(
                    pub.subscribers.values(), event, external_gather=self.external_gathers.get(event.__class__, None)
                )
            )
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        task = loop.create_task(
            dispatch(
                chain.from_iterable(
                    pub.subscribers.values() for pub in self.publishers.values() if pub.validate(event)
                ),
                event,
                external_gather=self.external_gathers.get(event.__class__, None),
            )
        )
        self._ref_tasks.add(task)
        task.add_done_callback(self._ref_tasks.discard)
        return task

    @overload
    def post(
        self, event: Resultable[T], publisher: str | Publisher | None = None
    ) -> asyncio.Task[Result[T] | None]: ...

    @overload
    def post(self, event: Any, publisher: str | Publisher | None = None) -> asyncio.Task[Result[Any] | None]: ...

    def post(self, event: Any, publisher: str | Publisher | None = None):
        """发布事件并返回第一个响应结果"""
        loop = asyncio.get_running_loop()
        if isinstance(publisher, str) and (pub := self.publishers.get(publisher)):
            task = loop.create_task(
                dispatch(
                    pub.subscribers.values(),
                    event,
                    return_result=True,
                    external_gather=self.external_gathers.get(event.__class__, None),
                )
            )
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        if isinstance(publisher, Publisher):
            task = loop.create_task(
                dispatch(
                    publisher.subscribers.values(),
                    event,
                    return_result=True,
                    external_gather=self.external_gathers.get(event.__class__, None),
                )
            )
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        if hasattr(event, "__publisher__") and (pub := self.publishers.get(event.__publisher__)):
            task = loop.create_task(
                dispatch(
                    pub.subscribers.values(),
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
                chain.from_iterable(
                    pub.subscribers.values() for pub in self.publishers.values() if pub.validate(event)
                ),
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
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ) -> Subscriber: ...

    @overload
    def on(
        self,
        events: type | tuple[type, ...],
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    @overload
    def on(
        self,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    def on(
        self,
        events: type | tuple[type, ...] | None = None,
        func: Callable[..., Any] | None = None,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ):
        if not (pub := publisher_ctx.get()):
            if not events:
                pub = self._backend_publisher
            else:
                events = events if isinstance(events, tuple) else (events,)
                if len(events) == 1 and (
                    hasattr(e := events[0], "__publisher__") and e.__publisher__ in self.publishers
                ):
                    pub = self.publishers[e.__publisher__]
                else:
                    pub = Publisher(f"global::{sorted(events, key=lambda e: id(e))}", *events)
        if pub.id in self.publishers:
            pub = self.publishers[pub.id]
        else:
            self.publishers[pub.id] = pub

        if not func:
            return pub.register(priority=priority, auxiliaries=auxiliaries, providers=providers, temporary=temporary)
        return pub.register(func, priority=priority, auxiliaries=auxiliaries, providers=providers, temporary=temporary)

    @overload
    def use(
        self,
        pub: str | Publisher,
        func: Callable[..., Any],
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ) -> Subscriber: ...

    @overload
    def use(
        self,
        pub: str | Publisher,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    @overload
    def use(
        self,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    def use(
        self,
        pub: str | Publisher | None = None,
        func: Callable[..., Any] | None = None,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ):
        if not pub:
            publisher = publisher_ctx.get() or self._backend_publisher
        else:
            publisher = pub if isinstance(pub, Publisher) else self.publishers[pub]
        if not func:
            return publisher.register(priority=priority, auxiliaries=auxiliaries, providers=providers, temporary=temporary)
        return publisher.register(func, priority=priority, auxiliaries=auxiliaries, providers=providers, temporary=temporary)


es = EventSystem()
