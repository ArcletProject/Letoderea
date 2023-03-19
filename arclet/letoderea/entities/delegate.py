from typing import List, Union, Dict, Any
from .subscriber import Subscriber
from ..utils import TEvent


class EventDelegate:
    """
    订阅器相关的处理器
    """

    subscribers: List[Subscriber]
    bind_event: TEvent
    priority: int

    def __init__(self, event: TEvent, priority: int = 16):
        self.subscribers = []
        self.bind_event = event
        self.priority = priority

    def __iadd__(self, other):
        if isinstance(other, Subscriber):
            if other.name in self.subscribers_names():
                raise ValueError(
                    f'Function "{other.name}" for event: '
                    f"{self.bind_event.__name__} has already registered!"
                )
            self.subscribers.append(other)
            return self
        elif isinstance(other, List):
            for sub in other:
                self.__iadd__(sub)
            return self

    def __eq__(self, other: Union["EventDelegate", TEvent]):
        if isinstance(other, EventDelegate):
            return all(
                [
                    other.subscribers == self.subscribers,
                    other.bind_event is self.bind_event,
                    other.priority == self.priority,
                ]
            )
        else:
            return other is self.bind_event

    def subscribers_names(self):
        return [i.name for i in self.subscribers]

    def parse_to_event(self, data: Dict[str, Any]):
        return self.bind_event(**{k: v for k, v in data.items() if k != "type"})
