from typing import Union, Dict, Optional, List, Any, TYPE_CHECKING
from .delegate import EventDelegate, Subscriber
from ..utils import Condition_T, Event_T
from .event import TemplateEvent
from .condition import TemplateCondition

if TYPE_CHECKING:
    from .. import EventSystem


class Publisher:
    external_conditions: List[Condition_T]
    internal_delegate: Dict[str, EventDelegate]
    priority: int

    def __init__(
            self,
            priority: int = 16,
            conditions: Optional[List[Condition_T]] = None,
            *delegates: Optional[EventDelegate]
    ):
        self.external_conditions = conditions or []
        self.internal_delegate = {}
        self.priority = priority
        if delegates:
            for delegate in delegates:
                self.__iadd__(delegate)

    def __iadd__(self, other: EventDelegate):
        _name = other.bind_event.__name__
        if _name in self.internal_delegate:
            self.internal_delegate[_name] += other.subscribers
        else:
            self.internal_delegate[_name] = other
        return self

    def __getitem__(self, item: Union[TemplateEvent, str]):
        if isinstance(item, TemplateEvent):
            return self.internal_delegate[item.__class__.__name__]
        return self.internal_delegate[item]

    def __contains__(self, item: Union[Event_T, EventDelegate, Subscriber, Condition_T]):
        if isinstance(item, TemplateCondition):
            for condition in self.external_conditions:
                if item == condition:
                    return True
            return False
        elif isinstance(item, Subscriber):
            for delegate in self.internal_delegate.values():
                if item in delegate.subscribers:
                    return True
            return False
        elif isinstance(item, EventDelegate):
            return item in self.internal_delegate.values()
        else:
            return item.__name__ in self.internal_delegate

    def equal_conditions(self, cl: List[Condition_T]):
        cl.sort(key=lambda x: id(x))
        self.external_conditions.sort(key=lambda x: id(x))
        return cl == self.external_conditions

    def on_event(self, event_system: "EventSystem"):
        target: Union[TemplateEvent, Dict[str, Any]] = event_system.current_event
        event_name = target.__class__.__name__
        if isinstance(target, dict):
            event_name = target.get('type')
        if event_name in self.internal_delegate.keys():
            if isinstance(target, TemplateEvent):
                event_system.loop.create_task(self.internal_delegate[event_name].executor(target))
            else:
                event_system.loop.create_task(self.internal_delegate[event_name].parse_to_event(target).executor())

    def remove_delegate(self, target: Union[str, Event_T]):
        if isinstance(target, str):
            del self.internal_delegate[target]
        elif isinstance(target, TemplateEvent):
            del self.internal_delegate[target.__class__.__name__]
        else:
            del self.internal_delegate[target.__name__]
