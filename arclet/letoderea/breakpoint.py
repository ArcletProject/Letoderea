import asyncio
from collections.abc import Awaitable
from typing import Callable, Generic, Optional, TypeVar, Union, overload, Any
from types import CoroutineType

from .exceptions import BLOCK
from .provider import TProviders
from .subscriber import Subscriber, RESULT
from .scope import on
from .typing import Contexts

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
    def __anext__(self: "_step_iter[CoroutineType[Any, Any, R1], None] | _step_iter[Awaitable[R1], None] | _step_iter[R1, None]") -> Awaitable[Optional[R1]]: ...

    @overload
    def __anext__(self: "_step_iter[CoroutineType[Any, Any, R1], D1] | _step_iter[Awaitable[R1], D1] | _step_iter[R1, D1]") -> Awaitable[Union[R1, D1]]: ...

    def __anext__(self):  # type: ignore
        return self.step.wait(default=self.default, timeout=self.timeout)


class StepOut(Generic[R]):

    def __init__(
        self,
        handler: Union[Subscriber[R], Callable[[], Subscriber[R]]],
        priority: int = 15,
        block: bool = False,
    ):
        self.handler = handler
        self.priority = priority
        self.block = block
        self.waiting = False
        self._dispose = False

    def dispose(self):  # pragma: no cover
        if not self._dispose:
            if isinstance(self.handler, Subscriber):
                self.handler.dispose()
            self._dispose = True

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
    async def wait(self: "StepOut[CoroutineType[Any, Any, R1]] | StepOut[Awaitable[R1]] | StepOut[R1]", *, timeout: float = 120) -> Optional[R1]: ...

    @overload
    async def wait(self: "StepOut[CoroutineType[Any, Any, R1]] | StepOut[Awaitable[R1]] | StepOut[R1]", *, default: Union[R1, D], timeout: float = 120) -> Union[R1, D]: ...

    async def wait(
        self,
        *,
        timeout: float = 0.0,
        default: Any = None,
    ):
        if self._dispose:
            raise RuntimeError("This StepOut instance has been disposed and cannot be used anymore.")
        self.waiting = True
        handler = self.handler if isinstance(self.handler, Subscriber) else self.handler()
        fut = asyncio.get_running_loop().create_future()

        async def _after(ctx: Contexts):
            if fut.done():
                return False
            res = ctx[RESULT]
            if res is not None and not fut.done():
                fut.set_result(res)
                if self.block:
                    return BLOCK

        dispose = handler.propagate(_after)
        old_priority = handler.priority
        handler.priority = self.priority

        try:
            return await asyncio.wait_for(fut, timeout) if timeout else await fut
        except asyncio.TimeoutError:
            return default
        finally:
            if not fut.done():  # pragma: no cover
                fut.cancel()
            dispose()
            handler.priority = old_priority
            if not isinstance(self.handler, Subscriber):
                handler.dispose()
            self.waiting = False


@overload
def step_out(event: type, handler: Callable[..., R], *, providers: Optional[TProviders] = None, priority: int = 15, block: bool = False) -> StepOut[R]: ...


@overload
def step_out(event: type, *, providers: Optional[TProviders] = None, priority: int = 15, block: bool = False) -> Callable[[Callable[..., R]], StepOut[R]]: ...


@overload
def step_out(*, priority: int = 15, block: bool = False) -> Callable[[Subscriber[R]], StepOut[R]]: ...


def step_out(event: Union[type, None] = None, handler: Optional[Callable[...,  R]] = None, providers: Optional[TProviders] = None, priority: int = 15, block: bool = False):

    if event is None:
        def decorator1(func: Subscriber[R], /) -> StepOut[R]:
            return StepOut(func, priority, block)
        return decorator1

    def decorator(func: Callable[..., R], /) -> StepOut[R]:
        return StepOut(lambda: on(event, func, priority=priority, providers=providers), priority, block)

    if handler is not None:
        return decorator(handler)
    return decorator
