from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Callable
from weakref import finalize

from .auxiliary import BaseAuxiliary
from .context import system_ctx, publisher_ctx
from .event import BaseEvent, get_auxiliaries, get_providers
from .handler import dispatch
from .provider import Param, Provider
from .publisher import Publisher
from .subscriber import Subscriber
from .typing import Contexts, TCallable


class BackendPublisher(Publisher):
    def validate(self, event: type[BaseEvent] | BaseEvent):
        return True


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

        class EventProvider(Provider[BaseEvent]):
            def validate(self, param: Param):
                return (
                    isinstance(param.annotation, type)
                    and issubclass(param.annotation, BaseEvent)
                ) or param.name == "event"

            async def __call__(self, context: Contexts) -> BaseEvent | None:
                return context.get("$event")

        class ContextProvider(Provider[Contexts]):
            def validate(self, param: Param):
                return param.annotation == Contexts

            async def __call__(self, context: Contexts) -> Contexts:
                return context
            
        self.global_providers.extend([EventProvider(), ContextProvider()])

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
        pubs = [self._backend_publisher]
        if isinstance(publisher, str) and (pub := self.publishers.get(publisher)):
            pubs.append(pub)
        elif isinstance(publisher, Publisher):
            pubs.append(publisher)
        else:
            pubs.extend(
                pub
                for pub in self.publishers.values()
                if pub.validate(event.__class__)  # type: ignore
            )
        subscribers = sum((pub.subscribers for pub in pubs), [])
        task = self.loop.create_task(dispatch(subscribers, event))
        task.add_done_callback(self._ref_tasks.discard)
        return task

    def on(
        self,
        *events: type,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider]] | None = None,
    ):
        auxiliaries = auxiliaries or []
        providers = providers or []

        def register_wrapper(exec_target: TCallable) -> TCallable:
            for event in events:
                select_pubs = [pub] if (pub := publisher_ctx.get()) else (
                    [pub for pub in self.publishers.values() if pub.validate(event)]  # type: ignore
                    or [self._backend_publisher]
                )
                for pub in select_pubs:
                    _providers = [
                        *self.global_providers,
                        *get_providers(event),
                        *pub.providers,
                        *providers,
                    ]
                    _auxiliaries = [
                        *auxiliaries,
                        *get_auxiliaries(event)
                    ]
                    pub.add_subscriber(
                        Subscriber(
                            exec_target,
                            priority=priority,
                            auxiliaries=_auxiliaries,
                            providers=_providers,
                        )
                    )

            return exec_target

        return register_wrapper
