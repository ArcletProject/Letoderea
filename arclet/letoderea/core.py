from __future__ import annotations

import asyncio
from typing import Callable

from .auxiliary import BaseAuxiliary
from .backend import BackendPublisher
from .context import event_ctx
from .event import BaseEvent, get_providers
from .exceptions import PropagationCancelled
from .handler import depend_handler
from .provider import ProvideMode, Provider
from .publisher import BasePublisher
from .subscriber import Subscriber
from .typing import Contexts
from .utils import group_dict


class EventSystem:
    _ref_tasks = set()
    _backend_publisher: BasePublisher = BackendPublisher()
    loop: asyncio.AbstractEventLoop
    publishers: list[BasePublisher]
    global_providers: list[Provider]

    def __init__(self, loop=None, fetch=True):
        self.loop = loop or asyncio.get_event_loop()
        if fetch:
            self.loop_task = self.loop.create_task(self._loop_fetch())
        self.publishers = []
        self.global_providers = []

        @self.global_providers.append
        class EventGenericProvider(Provider[BaseEvent], mode=ProvideMode.generic):
            async def __call__(self, context: Contexts) -> BaseEvent | None:
                return context.get("event")

        @self.global_providers.append
        class EventNameMatchProvider(Provider[BaseEvent], mode=ProvideMode.wildcard, target="event"):
            async def __call__(self, context: Contexts) -> BaseEvent | None:
                return context.get("event")

    async def _loop_fetch(self):
        while True:
            await asyncio.sleep(0.05)
            for publisher in self.publishers:
                if not (event := (await publisher.supply())):
                    continue
                await self.publish(event, publisher)

    def publish(self, event: BaseEvent, publisher: BasePublisher | None = None):
        publisher = publisher or self._backend_publisher
        subscribers = publisher.subscribers[event.__class__.__name__]
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
                name = event.__name__
                select_pub: BasePublisher
                for publisher in self.publishers:
                    if name in publisher.events:
                        select_pub = publisher
                        break
                else:
                    select_pub = self._backend_publisher
                _providers = [
                    *self.global_providers,
                    *get_providers(event),  # type: ignore
                    *providers,
                ]
                if not isinstance(exec_target, Subscriber):
                    exec_target = Subscriber(
                        exec_target,
                        priority=priority,
                        auxiliaries=auxiliaries,
                        providers=_providers,
                    )
                select_pub.add_subscriber(name, exec_target)

            return exec_target

        return register_wrapper
