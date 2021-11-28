import asyncio
from datetime import datetime
from typing import List, Union, Type, Dict, Any
from .entities.delegate import EventDelegate
from .entities.event import TemplateEvent
from .entities.publisher import Publisher
from .entities.decorator import TemplateDecorator
from .entities.subscriber import Subscriber
from .utils import Condition_T, search_event, event_class_generator


class EventSystem:
    loop: asyncio.AbstractEventLoop
    publisher_list: List[Publisher]
    safety_interval: float
    last_run: datetime
    current_event: Union[TemplateEvent, Dict[str, Any]]

    def __init__(
            self,
            *,
            loop: asyncio.AbstractEventLoop = None,
            interval: float = 0.00
    ):
        self.publisher_list = []
        self.loop = loop or asyncio.get_event_loop()
        self.safety_interval = interval
        self.last_run = datetime.now()

    def event_spread(self, target: Union[TemplateEvent, Dict[str, Any]]):
        if (datetime.now() - self.last_run).total_seconds() >= self.safety_interval:
            self.current_event = target
            try:
                for pub in self.publisher_generator():
                    pub.on_event(self)
            except asyncio.CancelledError:
                return
        self.last_run = datetime.now()

    def publisher_generator(self):
        able_pubs = list(
            filter(
                lambda x: all([condition.judge(self.current_event) for condition in x.external_conditions]),
                self.publisher_list
            )
        )
        able_pubs.sort(key=lambda x: x.priority)
        return able_pubs

    def get_publisher(self, target: Union[Type[TemplateEvent], Condition_T]):
        p_list = []
        for publisher in self.publisher_list:
            if target in publisher:
                p_list.append(publisher)
        if len(p_list) > 0:
            return p_list
        return False

    def remove_publisher(self, target: Publisher):
        self.publisher_list.remove(target)

    def register(
            self,
            event: Union[str, Type[TemplateEvent]],
            *,
            priority: int = 16,
            conditions: List[Condition_T] = None,
            decorators: List[TemplateDecorator] = None,
    ):
        if isinstance(event, str):
            name = event
            event = search_event(event)
            if not event:
                raise Exception(name + " cannot found!")

        events = [event]
        events.extend(event_class_generator(event))
        conditions = conditions or []
        decorators = decorators or []

        def register_wrapper(exec_target):
            if not isinstance(exec_target, Subscriber):
                exec_target = Subscriber(
                    callable_target=exec_target,
                    decorators=decorators
                )
            for e in events:
                may_publishers = self.get_publisher(e)
                _event_handler = EventDelegate(event=e)
                _event_handler += exec_target
                if not may_publishers:
                    self.publisher_list.append(Publisher(priority, conditions, _event_handler))
                else:
                    for m_publisher in may_publishers:
                        if m_publisher.equal_conditions(conditions):
                            m_publisher += _event_handler
                            break
                    else:
                        self.publisher_list.append(Publisher(priority, conditions, _event_handler))

            return exec_target

        return register_wrapper
