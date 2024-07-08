import asyncio
from asyncio import Future
from typing import Awaitable, Callable, Generic, List, Optional, Set, Type, TypeVar, Union, overload

from ..auxiliary import AuxType, BaseAuxiliary, auxilia
from ..core import EventSystem, system_ctx
from ..event import BaseEvent, get_auxiliaries, get_providers
from ..exceptions import PropagationCancelled
from ..handler import depend_handler
from ..provider import Provider
from ..publisher import Publisher, global_providers
from ..subscriber import Subscriber
from ..typing import TCallable, TTarget

_backend = {}
R = TypeVar("R")
R1 = TypeVar("R1")
D = TypeVar("D")
D1 = TypeVar("D1")


class _step_iter(Generic[R, D]):
    def __init__(self, step: "StepOut[R]", default: D, timeout: float):
        self.step = step
        self.default = default
        self.timeout = timeout

    def __aiter__(self):
        return self

    @overload
    def __anext__(self: "_step_iter[R1, None]") -> Awaitable[Optional[R1]]: ...

    @overload
    def __anext__(self: "_step_iter[R1, D1]") -> Awaitable[Union[R1, D1]]: ...

    def __anext__(self):  # type: ignore
        bp = _backend.setdefault(0, Breakpoint(system_ctx.get()))
        return bp.wait(self.step, timeout=self.timeout, default=self.default)


class StepOut(Generic[R]):
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
        self.providers = providers or []
        self.auxiliaries = auxiliaries or []
        self.priority = priority
        self.handler = handler or (lambda: None)  # type: ignore
        self.block = block

    def use(self, func: TCallable) -> TCallable:
        self.handler = func
        return func

    @overload
    def __call__(self, *, default: D, timeout: float = 120) -> _step_iter[R, D]: ...

    @overload
    def __call__(self, *, timeout: float = 120) -> _step_iter[R, None]: ...

    def __call__(
        self, *, timeout: float = 120, default: Optional[D] = None
    ) -> Union[_step_iter[R, D], _step_iter[R, None]]:
        """等待用户输入并返回结果

        参数:
            default: 超时时返回的默认值
            timeout: 等待超时时间
        """
        return _step_iter(self, default, timeout)  # type: ignore

    @overload
    async def wait(self, *, timeout: float = 120) -> Optional[R]: ...

    @overload
    async def wait(self, *, default: Union[R, D], timeout: float = 120) -> Union[R, D]: ...

    async def wait(
        self,
        *,
        timeout: float = 0.0,
        default: Union[R, D, None] = None,
    ) -> Union[R, D]:
        bp = _backend.setdefault(0, Breakpoint(system_ctx.get()))
        return await bp.wait(self, timeout, default=default)


def new_target(event_t: Type[BaseEvent], condition: StepOut, fut: Future):
    sub = Subscriber(
        condition.handler,
        providers=[
            *global_providers,
            *get_providers(event_t),
            *condition.providers,
        ],
        priority=condition.priority,
        auxiliaries=[
            *condition.auxiliaries,
            *get_auxiliaries(event_t),
        ],
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


class Breakpoint:
    es: EventSystem

    def __init__(self, event_system: EventSystem):
        self.es = event_system

    async def wait(
        self,
        condition: StepOut[R],
        timeout: float = 0.0,
        default: D = None,
    ) -> Union[R, D]:
        fut = asyncio.get_running_loop().create_future()
        publisher = Publisher("__breakpoint__publisher__", *condition.target)

        for et in condition.target:
            callable_target = new_target(et, condition, fut)  # type: ignore
            publisher.register(
                priority=condition.priority,
                auxiliaries=[auxilia(AuxType.judge, prepare=lambda interface: isinstance(interface.event, et))],
            )(callable_target)

        try:
            self.es.register(publisher)
            return await asyncio.wait_for(fut, timeout) if timeout else await fut
        except asyncio.TimeoutError:
            return default
        finally:
            if not fut.done():
                fut.cancel()
                publisher.subscribers.clear()
            self.es.publishers.pop(publisher.id, None)

    def __enter__(self):
        _backend[0] = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _backend.pop(0, None)
        return False
