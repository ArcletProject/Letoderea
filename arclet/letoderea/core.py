from __future__ import annotations

import asyncio
from itertools import chain
from typing import Any, Callable, TypeVar, overload
from weakref import finalize

from .handler import dispatch
from .publisher import Publisher, search_publisher, _publishers
from .scope import Scope, on, use, _scopes
from .typing import Contexts, Result, Resultable

T = TypeVar("T")


class EventSystem:

    def __init__(self):
        self._ref_tasks = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.on = on
        self.use = use

        def _remove(es):  # pragma: no cover
            for task in es._ref_tasks:
                if not task.done():
                    task.cancel()
            es._ref_tasks.clear()

        finalize(self, _remove, self)

    async def setup_fetch(self):
        self._ref_tasks.add(asyncio.create_task(self._loop_fetch()))

    async def _loop_fetch(self):
        while True:
            for publisher in _publishers.values():
                if not (event := (await publisher.supply())):
                    continue
                self.post(event)
            await asyncio.sleep(0.05)

    def publish(self, event: Any, scope: str | Scope | None = None, inherit_ctx: Contexts | None = None):
        """发布事件"""
        loop = self.loop or asyncio.get_running_loop()
        pub = search_publisher(event)
        if isinstance(scope, str) and ((sp := _scopes.get(scope)) and sp.available):
            task = loop.create_task(
                dispatch(
                    sp.iter_subscribers(pub),
                    event,
                    pub.supplier if pub else None,
                    inherit_ctx=inherit_ctx,
                )
            )
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        if isinstance(scope, Scope) and scope.available:
            task = loop.create_task(
                dispatch(
                    scope.iter_subscribers(pub),
                    event,
                    pub.supplier if pub else None,
                    inherit_ctx=inherit_ctx,
                )
            )
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        scopes = [sp for sp in _scopes.values() if sp.available]
        task = loop.create_task(
            dispatch(
                chain.from_iterable(sp.iter_subscribers(pub) for sp in scopes),
                event,
                pub.supplier if pub else None,
                inherit_ctx=inherit_ctx,
            )
        )
        self._ref_tasks.add(task)
        task.add_done_callback(self._ref_tasks.discard)
        return task

    @overload
    def post(self, event: Resultable[T], scope: str | Scope | None = None) -> asyncio.Task[Result[T] | None]: ...

    @overload
    def post(self, event: Any, scope: str | Scope | None = None) -> asyncio.Task[Result[Any] | None]: ...

    def post(self, event: Any, scope: str | Scope | None = None):
        """发布事件并返回第一个响应结果"""
        loop = self.loop or asyncio.get_running_loop()
        pub = search_publisher(event)
        if isinstance(scope, str) and ((sp := _scopes.get(scope)) and sp.available):
            task = loop.create_task(
                dispatch(
                    sp.iter_subscribers(pub),
                    event,
                    pub.supplier if pub else None,
                    return_result=True,
                )
            )
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        if isinstance(scope, Scope) and scope.available:
            task = loop.create_task(
                dispatch(
                    scope.iter_subscribers(pub),
                    event,
                    pub.supplier if pub else None,
                    return_result=True,
                )
            )
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        task = loop.create_task(
            dispatch(
                chain.from_iterable(sp.iter_subscribers(pub) for sp in _scopes.values() if sp.available),
                event,
                pub.supplier if pub else None,
                return_result=True,
            )
        )
        self._ref_tasks.add(task)
        task.add_done_callback(self._ref_tasks.discard)
        return task


es = EventSystem()


C = TypeVar("C")


@overload
def make_event(cls: type[C]) -> type[C]: ...


@overload
def make_event(*, name: str) -> Callable[[type[C]], type[C]]: ...


def make_event(cls: type[C] | None = None, *, name: str | None = None):

    def wrapper(_cls: type[C], /):
        annotation = {k: v for c in reversed(_cls.__mro__[:-1]) for k, v in getattr(c, "__annotations__", {}).items()}

        async def _gather(self: C, ctx: Contexts):
            return ctx.update({key: getattr(self, key, None) for key in annotation if key != "providers"})

        id_ = name or f"$event:{_cls.__module__}.{_cls.__name__}"
        parent_publisher = {getattr(c, "__publisher__", None) for c in _cls.__mro__[1:-1]}
        if hasattr(_cls, "__publisher__") and _cls.__publisher__ not in parent_publisher:  # type: ignore
            id_ = _cls.__publisher__  # type: ignore
        pub = Publisher(_cls, id_=id_, supplier=_gather)
        _cls.__publisher__ = pub.id  # type: ignore
        _cls.__context_gather__ = pub.supplier  # type: ignore
        return _cls  # type: ignore

    if cls:
        return wrapper(cls)
    return wrapper


def scope(self, id_: str | None = None):
    sp = Scope(id_)
    _scopes[sp.id] = sp
    return sp
