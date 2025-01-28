import asyncio
from asyncio import Future
from collections.abc import Awaitable
from typing import Callable, Generic, Optional, TypeVar, Union, overload

from .core import es
from .exceptions import PropagationCancelled
from .handler import generate_contexts
from .provider import Provider, get_providers, global_providers
from .subscriber import Subscriber
from .typing import TCallable, TTarget

R = TypeVar("R")
R1 = TypeVar("R1")
D = TypeVar("D")
D1 = TypeVar("D1")


def new_target(event_t: type, condition: "StepOut", fut: Future):
    sub = Subscriber(
        condition.handler,
        providers=[
            *global_providers,
            *get_providers(event_t),  # type: ignore
            *condition.providers,
        ],
        priority=condition.priority,
    )

    async def inner(event: event_t):  # type: ignore
        if fut.done():
            return False
        ctx = await generate_contexts(event)
        result = await sub.handle(ctx)
        if result is not None and not fut.done():
            fut.set_result(result)
            if condition.block:
                raise PropagationCancelled()

    return inner


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
        return self.step.wait(default=self.default, timeout=self.timeout)


class StepOut(Generic[R]):
    target: set[type]
    providers: list[Union[Provider, type[Provider]]]
    handler: TTarget[R]
    priority: int

    def __init__(
        self,
        events: list[type],
        handler: Optional[Union[Callable[..., Awaitable[R]], Callable[..., R]]] = None,
        providers: Optional[list[Union[Provider, type[Provider]]]] = None,
        priority: int = 15,
        block: bool = False,
    ):
        self.target = set(events)
        self.providers = providers or []
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
    ) -> Union[R, D, None]:
        fut = asyncio.get_running_loop().create_future()
        subscribers = []

        for et in self.target:
            callable_target = new_target(et, self, fut)  # type: ignore
            # aux = auxilia("step_out", lambda interface: isinstance(interface.event, et))
            subscribers.append(es.on(et, callable_target, priority=self.priority))
        try:
            return await asyncio.wait_for(fut, timeout) if timeout else await fut
        except asyncio.TimeoutError:
            return default
        finally:
            if not fut.done():
                fut.cancel()
            for sub in subscribers:
                sub.dispose()
            subscribers.clear()
