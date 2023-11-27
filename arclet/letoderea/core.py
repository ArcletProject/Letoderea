from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Callable
from weakref import finalize

from .auxiliary import BaseAuxiliary
from .context import publisher_ctx, system_ctx
from .event import BaseEvent
from .handler import dispatch
from .provider import Provider, ProviderFactory
from .publisher import BackendPublisher, Publisher
from .subscriber import Subscriber


class EventSystem:
    _ref_tasks = set()
    _backend_publisher: Publisher = BackendPublisher("__backend__publisher__")
    loop: asyncio.AbstractEventLoop
    publishers: dict[str, Publisher]

    def __init__(self, loop=None, fetch=True):
        self.loop = loop or asyncio.new_event_loop()
        if fetch:
            self.loop_task = self.loop.create_task(self._loop_fetch())
        self.publishers = {}
        self._token = system_ctx.set(self)

        def _remove(es):
            with suppress(Exception):
                es.loop_task.cancel()
                es.loop_task = None
            with suppress(Exception):
                system_ctx.reset(es._token)
            system_ctx.set(None)  # type: ignore

        finalize(self, _remove, self)

    async def _loop_fetch(self):
        while True:
            await asyncio.sleep(0.05)
            for publisher in self.publishers.values():
                if not (event := (await publisher.supply())):
                    continue
                await self.publish(event, publisher)

    def register(self, *publishers: Publisher):
        """注册发布者"""
        for publisher in publishers:
            self.publishers[publisher.id] = publisher

    def publish(self, event: BaseEvent, publisher: str | Publisher | None = None):
        pubs = []
        if isinstance(publisher, str) and (pub := self.publishers.get(publisher)):
            pubs.append(pub)
        elif isinstance(publisher, Publisher):
            pubs.append(publisher)
        else:
            pubs.extend(pub for pub in self.publishers.values() if pub.validate(event))  # type: ignore
        subscribers = sum((pub.subscribers for pub in pubs), [])
        task = self.loop.create_task(dispatch(subscribers, event))
        task.add_done_callback(self._ref_tasks.discard)
        return task

    def on(
        self,
        *events: type,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
    ):
        if not (pub := publisher_ctx.get()):
            pub = Publisher("temp", *events) if events else self._backend_publisher
        if pub.id in self.publishers:
            pub = self.publishers[pub.id]
        else:
            self.publishers[pub.id] = pub

        def wrapper(exec_target: Callable) -> Subscriber:
            return pub.register(
                priority,
                auxiliaries,
                providers,
            )(exec_target)

        return wrapper
