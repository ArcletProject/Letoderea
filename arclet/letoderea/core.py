from __future__ import annotations

import asyncio
from typing import Callable
from weakref import finalize
from contextlib import suppress

from .auxiliary import BaseAuxiliary
from .context import event_ctx, system_ctx
from .event import BaseEvent, get_providers
from .exceptions import PropagationCancelled
from .handler import depend_handler
from .provider import Provider, Param
from .publisher import Publisher
from .subscriber import Subscriber
from .typing import Contexts
from .utils import group_dict


class BackendPublisher(Publisher):
    def add_subscriber(self, event: type[BaseEvent], subscriber: Subscriber) -> None:
        self.subscribers.setdefault(event, []).append(subscriber)

    def remove_subscriber(self, event: type[BaseEvent], subscriber: Subscriber) -> None:
        self.subscribers.setdefault(event, []).remove(subscriber)
        if not self.subscribers[event]:
            del self.subscribers[event]


class EventSystem:
    _ref_tasks = set()
    _backend_publisher: Publisher = BackendPublisher("__backend__publisher__")
    loop: asyncio.AbstractEventLoop
    publishers: dict[str, Publisher]
    global_providers: list[Provider]

    def __init__(self, loop=None, fetch=True):
        self.loop = loop or asyncio.get_event_loop()
        if fetch:
            self.loop_task = self.loop.create_task(self._loop_fetch())
        self.publishers = {}
        self.global_providers = []
        self._token = system_ctx.set(self)

        def _remove(es):
            with suppress(Exception):
                es.loop_task.cancel()
                es.loop_task = None
            with suppress(Exception):
                system_ctx.reset(es._token)
            system_ctx.set(None)  # type: ignore
        finalize(self, _remove, self)

        @self.global_providers.append
        class EventProvider(Provider[BaseEvent]):
            def validate(self, param: Param):
                return issubclass(param.annotation, BaseEvent) or param.name == "event"

            async def __call__(self, context: Contexts) -> BaseEvent | None:
                return context.get("event")

        @self.global_providers.append
        class ContextProvider(Provider[Contexts]):

            def validate(self, param: Param):
                return param.annotation == Contexts

            async def __call__(self, context: Contexts) -> Contexts:
                return context

    async def _loop_fetch(self):
        while True:
            await asyncio.sleep(0.05)
            for publisher in self.publishers.values():
                if not (event := (await publisher.supply())):
                    continue
                await self.publish(event, publisher)

    def add_publisher(self, publisher: Publisher):
        self.publishers[publisher.id] = publisher

    def publish(self, event: BaseEvent, publisher: str | Publisher | None = None):
        if isinstance(publisher, str):
            publisher = self.publishers.get(publisher)
        if publisher is None:
            publisher = self._backend_publisher
        subscribers = publisher.subscribers[event.__class__]
        task = self.loop.create_task(self.dispatch(subscribers, event))
        task.add_done_callback(self._ref_tasks.discard)
        return task

    async def dispatch(self, subscribers: list[Subscriber], event: BaseEvent):
        grouped: dict[int, list[Subscriber]] = group_dict(subscribers, lambda x: x.priority)
        with event_ctx.use(event):
            for _, current_subs in sorted(grouped.items(), key=lambda x: x[0]):
                tasks = [
                    depend_handler(subscriber, event)
                    for subscriber in current_subs
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if result is PropagationCancelled:
                        return

    def register(
        self,
        *events: type[BaseEvent],
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider]] | None = None,
    ):
        auxiliaries = auxiliaries or []
        providers = providers or []

        def register_wrapper(exec_target: Callable) -> Subscriber:
            for event in events:
                select_pub: Publisher
                for publisher in self.publishers.values():
                    if event in publisher.events:
                        select_pub = publisher
                        break
                else:
                    select_pub = self._backend_publisher
                _providers = [
                    *self.global_providers,
                    *get_providers(event),  # type: ignore
                    *select_pub.providers.get(event, []),
                    *providers,
                ]
                if not isinstance(exec_target, Subscriber):
                    exec_target = Subscriber(
                        exec_target,
                        priority=priority,
                        auxiliaries=auxiliaries,
                        providers=_providers,
                    )
                select_pub.add_subscriber(event, exec_target)  # type: ignore

            return exec_target

        return register_wrapper
