import asyncio
from typing import List, Union, Dict, Any, Type

from .builtin.publisher import TemplatePublisher
from .entities.auxiliary import BaseAuxiliary
from .entities.delegate import EventDelegate
from .entities.event import TemplateEvent
from .entities.publisher import Publisher
from .entities.subscriber import Subscriber
from .exceptions import PropagationCancelled
from .handler import await_exec_target, event_ctx
from .utils import search_event, event_class_generator, group_dict, gather_inserts


class EventSystem:
    _ref_tasks = set()
    loop: asyncio.AbstractEventLoop
    publishers: List[Publisher]
    _background_publisher: Publisher

    def __init__(self, *, loop: asyncio.AbstractEventLoop = None):
        self.loop = loop or asyncio.new_event_loop()
        self.publishers = []
        self._background_publisher = TemplatePublisher()
        self.publishers.append(self._background_publisher)

    def event_publish(
        self, event: Union[TemplateEvent, Dict[str, Any]], publisher: Publisher = None
    ):
        publishers = [publisher] if publisher else self.publishers
        delegates = []
        for publisher in publishers:
            delegates.extend(publisher.require(event.__class__) or [])
        task = self.loop.create_task(self.delegate_exec(delegates, event))
        task.add_done_callback(self._ref_tasks.discard)
        return task

    @staticmethod
    async def delegate_exec(delegates: List[EventDelegate], event: TemplateEvent):
        event_chains = gather_inserts(event)
        grouped: Dict[int, EventDelegate] = group_dict(delegates, lambda x: x.priority)
        with event_ctx.use(event):
            for _, current_delegate in sorted(grouped.items(), key=lambda x: x[0]):
                coroutine = [
                    await_exec_target(target, event_chains)
                    for target in current_delegate.subscribers
                ]
                results = await asyncio.gather(*coroutine, return_exceptions=True)
                for result in results:
                    if result is PropagationCancelled:
                        return

    def register(
        self,
        event: Union[str, Type[TemplateEvent]],
        *,
        priority: int = 16,
        auxiliaries: List[BaseAuxiliary] = None,
        publisher: Publisher = None,
        inline_arguments: Dict[str, Any] = None,
        bypass: bool = False,
    ):
        if isinstance(event, str):
            name = event
            event = search_event(event)
            if not event:
                raise Exception(name + " cannot found!")

        events = [event]
        if bypass:
            events.extend(event_class_generator(event))
        auxiliaries = auxiliaries or []
        inline_arguments = inline_arguments or {}
        publisher = publisher or self._background_publisher

        def register_wrapper(exec_target):
            if not isinstance(exec_target, Subscriber):
                exec_target = Subscriber(
                    callable_target=exec_target,
                    auxiliaries=auxiliaries,
                    **inline_arguments,
                )
            for e in events:
                if may_delegate := publisher.require(e, priority):
                    may_delegate += exec_target
                else:
                    _event_handler = EventDelegate(e, priority)
                    _event_handler += exec_target
                    publisher.add_delegate(_event_handler)
            return exec_target

        return register_wrapper
