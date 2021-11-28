import asyncio
from typing import List, Union, Dict, Any
from .subscriber import Subscriber
from ..exceptions import PropagationCancelled
from ..handler import await_exec_target
from ..utils import Event_T


class EventDelegate:
    """
    订阅器相关的处理器
    """
    subscribers: List[Subscriber]
    bind_event: Event_T

    def __init__(self, event: Event_T):
        self.subscribers = []
        self.bind_event = event

    def __iadd__(self, other):
        if isinstance(other, Subscriber):
            if other.name in self.subscribers_names():
                raise ValueError(f"Function \"{other.name}\" for event: "
                                 f"{self.bind_event.__name__} has already registered!")
            self.subscribers.append(other)
            return self
        elif isinstance(other, List):
            for sub in other:
                self.__iadd__(sub)
            return self

    def __eq__(self, other: Union["EventDelegate", Event_T]):
        if isinstance(other, EventDelegate):
            return all([other.subscribers == self.subscribers, other.bind_event is self.bind_event])
        else:
            return other is self.bind_event

    def subscribers_names(self):
        return [i.name for i in self.subscribers]

    def parse_to_event(self, data: Union[Event_T, Dict[str, Any]]):
        if isinstance(data, dict):
            setattr(self, "wait_event", self.bind_event(**{k: v for k, v in data.items() if k != "type"}))
            return self
        setattr(self, "wait_event", data)
        return self

    async def executor(self, event: Event_T = None):
        current_event = getattr(self, "wait_event", event)
        event_params = current_event.get_params
        # self.subscribers.sort(key=lambda x: x.priority)
        coroutine = [
            await_exec_target(
                target,
                event_params
            )
            for target in self.subscribers
        ]
        (results, _) = await asyncio.wait(coroutine)
        for task in results:
            if task.exception().__class__ is PropagationCancelled:
                break
