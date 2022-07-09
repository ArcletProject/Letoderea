from typing import Type, Dict, List
from ..builtin.publisher import TemplatePublisher
from ..entities.subscriber import Subscriber
from .. import EventSystem, TemplateEvent
from .stepout import StepOut
from ..entities.delegate import EventDelegate


class Breakpoint:
    event_system: EventSystem
    step_out_publisher: TemplatePublisher
    step_delegates: List[EventDelegate]

    def __init__(self, event_system: EventSystem, priority: int = 15):
        self.event_system = event_system
        self.step_out_publisher = TemplatePublisher()
        self.event_system.publishers.append(self.step_out_publisher)
        self._step_outs: Dict[Type[TemplateEvent], List[StepOut]] = {}
        self.priority = priority
        self.step_delegates = []

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
            for step in self._step_outs[event_type]:
                step.future.cancel()
            self._step_outs[event_type].clear()
            for delegate in self.step_delegates:
                self.step_out_publisher.remove_delegate(delegate)
            self.step_delegates.clear()

    def new_subscriber(self, event_type, step_out_condition):
        async def _():
            for step in self._step_outs[event_type]:
                if await step.make_done():
                    break
        subscriber = Subscriber(_, auxiliaries=[step_out_condition])
        delegate = EventDelegate(event_type, priority=15)
        delegate += subscriber
        self.step_out_publisher.add_delegate(delegate)
        self.step_delegates.append(delegate)

    def __call__(self, step_out_condition: StepOut, timeout: float = 0.):
        return self.wait(step_out_condition, timeout)
