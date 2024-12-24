from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from itertools import chain
from contextlib import contextmanager
from typing import Any, Awaitable, Callable, TypeVar, overload
from weakref import finalize

from .auxiliary import BaseAuxiliary
from .event import BaseEvent
from .context import scope_ctx
from .handler import dispatch
from .provider import Provider, ProviderFactory
from .publisher import ExternalPublisher, Publisher, _publishers, _backend_publisher
from .subscriber import Subscriber
from .scope import Scope
from .typing import Contexts, Result, Resultable

T = TypeVar("T")


class EventSystem:
    _ref_tasks = set()
    _global_scope = Scope("$global")
    external_gathers: dict[type, Callable[[Any], Awaitable[Contexts]]]

    def __init__(self):
        self.scopes: dict[str, Scope] = {"$global": self._global_scope}
        self.external_gathers = {}

        def _remove(es):
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

    @contextmanager
    def scope(self, id_: str | None = None):
        sp = Scope(id_)
        self.scopes[sp.id] = sp
        with sp.context():
            yield sp

    def define(
        self,
        target: type[T],
        name: str | None = None,
        supplier: Callable[[T], Mapping[str, Any]] | None = None,
    ) -> Publisher:
        if name and name in _publishers:
            return _publishers[name]
        if hasattr(target, "__publisher__"):
            _id = target.__publisher__  # type: ignore
        else:
            _id = f"$event:{target.__name__}"
        if _id in _publishers:
            return _publishers[_id]
        if issubclass(target, BaseEvent):
            publisher = Publisher(target, name)
        else:
            publisher = ExternalPublisher(target, name, supplier)
            self.external_gathers[target] = publisher.external_gather
        return publisher

    def publish(self, event: Any, scope: str | Scope | None = None):
        """发布事件"""
        loop = asyncio.get_running_loop()
        if hasattr(event, "__publisher__") and (pub := _publishers.get(event.__publisher__)):
            publisher_id = pub.id
        else:
            publisher_id = next((pub.id for pub in _publishers.values() if pub.validate(event)), _backend_publisher.id)
        if isinstance(scope, str) and ((sp := self.scopes.get(scope)) and sp.available):
            task = loop.create_task(dispatch(sp.iter_subscribers(publisher_id), event, external_gather=self.external_gathers.get(event.__class__, None),))
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        if isinstance(scope, Scope) and scope.available:
            task = loop.create_task(dispatch(scope.iter_subscribers(publisher_id), event, external_gather=self.external_gathers.get(event.__class__, None),))
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        task = loop.create_task(
            dispatch(
                chain.from_iterable(
                    sp.iter_subscribers(publisher_id) for sp in self.scopes.values() if sp.available
                ),
                event,
                external_gather=self.external_gathers.get(event.__class__, None),
            )
        )
        self._ref_tasks.add(task)
        task.add_done_callback(self._ref_tasks.discard)
        return task

    @overload
    def post(
        self, event: Resultable[T], scope: str | Scope | None = None
    ) -> asyncio.Task[Result[T] | None]: ...

    @overload
    def post(self, event: Any, scope: str | Scope | None = None) -> asyncio.Task[Result[Any] | None]: ...

    def post(self, event: Any, scope: str | Scope | None = None):
        """发布事件并返回第一个响应结果"""
        loop = asyncio.get_running_loop()
        if hasattr(event, "__publisher__") and (pub := _publishers.get(event.__publisher__)):
            publisher_id = pub.id
        else:
            publisher_id = next((pub.id for pub in _publishers.values() if pub.validate(event)), _backend_publisher.id)
        if isinstance(scope, str) and ((sp := self.scopes.get(scope)) and sp.available):
            task = loop.create_task(dispatch(sp.iter_subscribers(publisher_id), event, return_result=True, external_gather=self.external_gathers.get(event.__class__, None),))
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        if isinstance(scope, Scope) and scope.available:
            task = loop.create_task(dispatch(scope.iter_subscribers(publisher_id), event, return_result=True, external_gather=self.external_gathers.get(event.__class__, None),))
            self._ref_tasks.add(task)
            task.add_done_callback(self._ref_tasks.discard)
            return task
        task = loop.create_task(
            dispatch(
                chain.from_iterable(
                    sp.iter_subscribers(publisher_id) for sp in self.scopes.values() if sp.available
                ),
                event,
                return_result=True,
                external_gather=self.external_gathers.get(event.__class__, None),
            )
        )
        self._ref_tasks.add(task)
        task.add_done_callback(self._ref_tasks.discard)
        return task

    @overload
    def on(
        self,
        events: type | tuple[type, ...],
        func: Callable[..., Any],
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ) -> Subscriber: ...

    @overload
    def on(
        self,
        events: type | tuple[type, ...],
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    @overload
    def on(
        self,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    def on(
        self,
        events: type | tuple[type, ...] | None = None,
        func: Callable[..., Any] | None = None,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ):
        if events:
            for target in (events if isinstance(events, tuple) else (events,)):
                self.define(target)
        if not (scope := scope_ctx.get()):
            scope = self._global_scope
        if not func:
            return scope.register(
                events=events, priority=priority, auxiliaries=auxiliaries, providers=providers, temporary=temporary
            )
        return scope.register(
            func, events=events, priority=priority, auxiliaries=auxiliaries, providers=providers, temporary=temporary
        )

    @overload
    def use(
        self,
        pub: str | Publisher,
        func: Callable[..., Any],
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ) -> Subscriber: ...

    @overload
    def use(
        self,
        pub: str | Publisher,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ) -> Callable[[Callable[..., Any]], Subscriber]: ...

    def use(
        self,
        pub: str | Publisher,
        func: Callable[..., Any] | None = None,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: (
            Sequence[Provider[Any] | type[Provider[Any]] | ProviderFactory | type[ProviderFactory]] | None
        ) = None,
        temporary: bool = False,
    ):
        if not (scope := scope_ctx.get()):
            scope = self._global_scope
        if not func:
            return scope.register(
                priority=priority, auxiliaries=auxiliaries, providers=providers, temporary=temporary, publisher=pub
            )
        return scope.register(
            func, priority=priority, auxiliaries=auxiliaries, providers=providers, temporary=temporary, publisher=pub
        )


es = EventSystem()


C = TypeVar("C")


@overload
def make_event(cls: type[C]) -> type[C]: ...


@overload
def make_event(*, name: str) -> Callable[[type[C]], type[C]]: ...


def make_event(cls: type[C] | None = None, *, name: str | None = None):

    def wrapper(_cls: type[C], /):

        if not hasattr(_cls, "__annotations__"):
            raise ValueError(f"@make_event can only take effect for class with attribute annotations, not {_cls}")

        async def _gather(self, context: Contexts):
            for key in self.__annotations__:
                if key in ("providers", "auxiliaries"):
                    continue
                context[key] = getattr(self, key, None)

        _cls.gather = _gather  # type: ignore
        _cls.__publisher__ = es.define(_cls, name).id  # type: ignore
        return _cls  # type: ignore

    if cls:
        return wrapper(cls)
    return wrapper
