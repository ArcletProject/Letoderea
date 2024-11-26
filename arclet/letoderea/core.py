from __future__ import annotations

import asyncio
from typing import Any, Callable, TypeVar, overload
from weakref import finalize
from itertools import chain

from .auxiliary import BaseAuxiliary
from .context import publisher_ctx
from .handler import dispatch
from .provider import Provider, ProviderFactory
from .publisher import BackendPublisher, ExternalPublisher, Publisher
from .subscriber import Subscriber

T = TypeVar("T")


class EventSystem:
    _ref_tasks = set()
    _backend_publisher: Publisher = BackendPublisher("__backend__publisher__")
    publishers: dict[str, Publisher]

    def __init__(self):
        self.publishers = {}

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
        target: type[T],
        supplier: Callable[[T], dict[str, Any]] | None = None,
        predicate: Callable[[T], bool] | None = None,
    ):
        publisher = ExternalPublisher(target, supplier, predicate)
        self.register(publisher)
        return publisher

    def post(self, event: Any, publisher: str | Publisher | None = None):
        loop = asyncio.get_running_loop()
        if isinstance(publisher, str) and (pub := self.publishers.get(publisher)):
            task = loop.create_task(dispatch(pub.subscribers, event))
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        if isinstance(publisher, Publisher):
            task = loop.create_task(dispatch(publisher.subscribers, event))
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        task = loop.create_task(
            dispatch(
                chain.from_iterable(
                    pub.subscribers for pub in self.publishers.values() if pub.validate(event)
                ),
                event
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
        providers: list[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
    ) -> Subscriber:
        ...

    @overload
    def on(
        self,
        events: type | tuple[type, ...],
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
    ) -> Callable[[Callable[..., Any]], Subscriber]:
        ...

    def on(
        self,
        events: type | tuple[type, ...],
        func: Callable[..., Any] | None = None,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
    ):
        events = events if isinstance(events, tuple) else (events,)
        if not (pub := publisher_ctx.get()):
            pub = Publisher("temp", *events) if events else self._backend_publisher
        if pub.id in self.publishers:
            pub = self.publishers[pub.id]
        else:
            self.publishers[pub.id] = pub

        if not func:
            return pub.register(priority=priority, auxiliaries=auxiliaries, providers=providers)
        return pub.register(func, priority=priority, auxiliaries=auxiliaries, providers=providers)


es = EventSystem()
