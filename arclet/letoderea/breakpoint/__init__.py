from typing import Type, Dict, List
from ..entities.subscriber import Subscriber
from .. import EventSystem, TemplateEvent
from .stepout import StepOut
from ..entities.publisher import Publisher
from ..entities.delegate import EventDelegate


class Breakpoint:
    event_system: EventSystem
    step_publishers: List[Publisher]

    def __init__(self, event_system: EventSystem, priority: int = 15):
        self.event_system = event_system
        self._step_outs: Dict[Type[TemplateEvent], List[StepOut]] = {}
        self.priority = priority
        self.step_publishers = []

    async def wait(
            self,
            step_out_condition: StepOut,
            timeout: float = 0.,
    ):
        event_type = step_out_condition.event_type
        self.new_subscriber(event_type, step_out_condition)
        if event_type not in self._step_outs:
            self._step_outs[event_type] = [step_out_condition]
        else:
            self._step_outs[event_type].append(step_out_condition)
        try:
            return await step_out_condition.wait(timeout)
        finally:
            for pub in self.event_system.get_publisher(step_out_condition):
                self.event_system.remove_publisher(pub)
            if step_out_condition.done():
                for step in self._step_outs[event_type]:
                    step.future.cancel()
                self._step_outs[event_type].clear()
            else:
                for pub in self.step_publishers:
                    self.event_system.remove_publisher(pub)

    def new_subscriber(self, event_type, step_out_condition):
        async def _():
            for step in self._step_outs[event_type]:
                if await step.make_done():
                    break

        subscriber = Subscriber.set()(_)
        delegate = EventDelegate(event_type)
        delegate += subscriber
        publisher = Publisher(15, [step_out_condition], delegate)
        self.event_system.publisher_list.append(publisher)
        self.step_publishers.append(publisher)

    def __call__(self, step_out_condition: StepOut, timeout: float = 0.):
        return self.wait(step_out_condition, timeout)

