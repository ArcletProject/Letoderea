import asyncio
from asyncio import Future
from typing import Any, Callable, List, Optional, Set, Type, Union

from ..auxiliary import SCOPE, AuxType, BaseAuxiliary
from ..core import BackendPublisher, EventSystem
from ..event import BaseEvent
from ..exceptions import PropagationCancelled
from ..handler import depend_handler
from ..provider import Provider
from ..typing import Contexts, TCallable


class StepOut(BaseAuxiliary):
    target: Set[Type[BaseEvent]]
    providers: List[Union[Provider, Type[Provider]]]
    auxiliaries: List[BaseAuxiliary]
    handler: Callable[..., Any]
    priority: int

    def __init__(
        self,
        events: List[Type[BaseEvent]],
        providers: Optional[List[Union[Provider, Type[Provider]]]] = None,
        auxiliaries: Optional[List[BaseAuxiliary]] = None,
        priority: int = 15,
        handler: Optional[Callable[..., Any]] = None,
    ):
        self.target = set(events)
        super().__init__(AuxType.judge)
        self.providers = providers or []
        self.auxiliaries = auxiliaries or []
        self.priority = priority
        self.handler = handler or (lambda: None)

    @property
    def available_scopes(self) -> Set[SCOPE]:
        return {"prepare"}

    async def __call__(self, scope: SCOPE, context: Contexts):
        return type(context["event"]) in self.target

    def use(self, func: TCallable) -> TCallable:
        self.handler = func
        return func


class Breakpoint:
    es: EventSystem
    publisher: BackendPublisher

    def __init__(self, event_system: EventSystem):
        self.es = event_system
        self.publisher = BackendPublisher("builtin.breakpoint")
        self.es.add_publisher(self.publisher)

    async def wait(
        self,
        condition: StepOut,
        timeout: float = 0.0,
    ):
        fut = self.es.loop.create_future()

        for et in condition.target:
            callable_target = self.new_target(et, condition, fut)  # type: ignore
            self.es.register(
                et,  # type: ignore
                priority=condition.priority,
                auxiliaries=[condition],
                publisher=self.publisher,
            )(callable_target)

        try:
            return await asyncio.wait_for(fut, timeout) if timeout else await fut
        except asyncio.TimeoutError:
            return None
        finally:
            if not fut.done():
                self.publisher.subscribers.clear()

    def new_target(self, event_t: Type[BaseEvent], condition: StepOut, fut: Future):

        sub = self.es.register(
            event_t,  # type: ignore
            priority=condition.priority,
            auxiliaries=condition.auxiliaries,
            providers=condition.providers,
            publisher=self.publisher,
        )(condition.handler)
        self.publisher.remove_subscriber(event_t, sub)  # type: ignore

        async def inner(event: event_t):
            if fut.done():
                return False

            result = await depend_handler(sub, event)
            if result is not None and not fut.done():
                fut.set_result(result)
                raise PropagationCancelled()

        return inner

    def __call__(self, condition: StepOut, timeout: float = 0.0):
        return self.wait(condition, timeout)
