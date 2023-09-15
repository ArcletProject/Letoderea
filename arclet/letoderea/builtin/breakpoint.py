import asyncio
from asyncio import Future
from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)

from ..auxiliary import AuxType, BaseAuxiliary, Scope
from ..core import BackendPublisher, EventSystem, system_ctx
from ..event import BaseEvent, get_providers, get_auxiliaries
from ..subscriber import Subscriber
from ..exceptions import PropagationCancelled
from ..handler import depend_handler
from ..provider import Provider
from ..typing import Contexts, TCallable, TTarget

_backend = {}
R = TypeVar("R")
D = TypeVar("D")


class _step_iter(AsyncIterator[R]):
    def __init__(self, step: "StepOut[R]"):
        self.step = step

    def __anext__(self) -> Awaitable[R]:
        bp = _backend.setdefault(0, Breakpoint(system_ctx.get()))
        return bp(self.step)


class StepOut(BaseAuxiliary, Generic[R]):
    target: Set[type]
    providers: List[Union[Provider, Type[Provider]]]
    auxiliaries: List[BaseAuxiliary]
    handler: TTarget[R]
    priority: int

    def __init__(
        self,
        events: List[type],
        handler: Optional[Union[Callable[..., Awaitable[R]], Callable[..., R]]] = None,
        providers: Optional[List[Union[Provider, Type[Provider]]]] = None,
        auxiliaries: Optional[List[BaseAuxiliary]] = None,
        priority: int = 15,
        block: bool = False,
    ):
        self.target = set(events)
        super().__init__(AuxType.judge)
        self.providers = providers or []
        self.auxiliaries = auxiliaries or []
        self.priority = priority
        self.handler = handler or (lambda: None)  # type: ignore
        self.block = block

    @property
    def scopes(self) -> Set[Scope]:
        return {Scope.prepare}

    async def __call__(self, scope: Scope, context: Contexts):
        return type(context["$event"]) in self.target

    def use(self, func: TCallable) -> TCallable:
        self.handler = func
        return func

    def __aiter__(self) -> _step_iter[R]:
        return _step_iter(self)


class Breakpoint:
    es: EventSystem
    publisher: BackendPublisher

    def __init__(self, event_system: EventSystem):
        self.es = event_system
        self.publisher = BackendPublisher("builtin.breakpoint")

    async def wait(
        self,
        condition: StepOut[R],
        timeout: float = 0.0,
        default: D = None,
    ) -> Union[R, D]:
        fut = self.es.loop.create_future()

        for et in condition.target:
            callable_target = self.new_target(et, condition, fut)  # type: ignore
            self.publisher.subscribers.append(
                Subscriber(
                    callable_target,
                    providers=[*self.es.global_providers, *get_providers(et)],
                    priority=condition.priority,
                    auxiliaries=[condition],
                )
            )

        try:
            self.es.register(self.publisher)
            return await asyncio.wait_for(fut, timeout) if timeout else await fut
        except asyncio.TimeoutError:
            return default
        finally:
            if not fut.done():
                self.publisher.subscribers.clear()
            self.es.publishers.pop(self.publisher.id)

    def new_target(self, event_t: Type[BaseEvent], condition: StepOut, fut: Future):

        sub = Subscriber(
            condition.handler,
            providers=[
                *self.es.global_providers,
                *get_providers(event_t),
                *condition.providers
            ],
            priority=condition.priority,
            auxiliaries=[
                *condition.auxiliaries,
                *get_auxiliaries(event_t),
            ]
        )

        async def inner(event: event_t):
            if fut.done():
                return False

            result = await depend_handler(sub, event)
            if result is not None and not fut.done():
                fut.set_result(result)
                if condition.block:
                    raise PropagationCancelled()

        return inner

    def __call__(self, condition: StepOut[R], timeout: float = 0.0, default: D = None) -> Awaitable[Union[R, D]]:
        return self.wait(condition, timeout, default=default)
