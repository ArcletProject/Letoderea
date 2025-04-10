from __future__ import annotations

import asyncio
import atexit
from collections.abc import Awaitable, Iterable
from dataclasses import dataclass
from itertools import chain
from typing import Any, Callable, Coroutine, Literal, TypeVar, overload

from .exceptions import STOP, BLOCK
from .publisher import Publisher, gather, define, _publishers
from .provider import get_providers, provide
from .scope import Scope, on, use, _scopes  # noqa: F401
from .subscriber import Subscriber
from .typing import Contexts, Force, Result, Resultable, generate_contexts


T = TypeVar("T")


@dataclass(frozen=True)
class ExceptionEvent:
    origin: Any
    subscriber: Subscriber
    exception: BaseException

    providers = [
        provide(
            BaseException,
            "exception",
            validate=lambda p: (p.annotation and issubclass(p.annotation, BaseException)) or p.name == "exception"
        )
    ]


exc_pub = define(ExceptionEvent, name="internal/exception")


@gather
async def _(event: ExceptionEvent, context: Contexts):
    return context.update(exception=event.exception, origin=event.origin, subscriber=event.subscriber)


async def publish_exc_event(event: ExceptionEvent):
    scopes = [sp for sp in _scopes.values() if sp.available]
    subs = [slot for sp in scopes for slot in sp.subscribers.values() if slot[1] != "$backend"]
    await dispatch(subs, event)


@overload
async def dispatch(slots: Iterable[tuple[Subscriber, str]], event: Any, inherit_ctx: Contexts | None = None) -> None: ...


@overload
async def dispatch(slots: Iterable[tuple[Subscriber, str]], event: Any, inherit_ctx: Contexts | None = None, *, return_result: Literal[True]) -> Result | None: ...


async def dispatch(slots: Iterable[tuple[Subscriber, str]], event: Any, inherit_ctx: Contexts | None = None, *, return_result: bool = False):
    grouped: dict[tuple[int, str], list[Subscriber]] = {}
    context_map: dict[str, Contexts] = {}
    if pub := _publishers.get(getattr(event, "__publisher__", f"$event:{type(event).__module__}{type(event).__name__}")):
        pubs = {pub.id: pub}
    else:
        pubs = {pub.id: pub for pub in _publishers.values() if pub.validate(event)}
    for sub, pub_id in slots:
        if pub_id != "$backend" and pub_id not in pubs:
            continue
        if pub_id not in context_map:
            context_map[pub_id] = await generate_contexts(event, None if pub_id == "$backend" else pubs[pub_id].supplier, inherit_ctx)
        if ((priority := sub.priority), pub_id) not in grouped:
            grouped[(priority, pub_id)] = []
        grouped[(priority, pub_id)].append(sub)
    for (priority, pub_id) in sorted(grouped.keys(), key=lambda x: x[0]):
        contexts = context_map[pub_id]
        tasks = [subscriber.handle(contexts.copy()) for subscriber in grouped[(priority, pub_id)]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for _i, result in enumerate(results):
            if result is None:
                continue
            if result is BLOCK:
                return
            if result is STOP:
                continue
            if isinstance(result, BaseException):
                if isinstance(event, ExceptionEvent):
                    return
                await publish_exc_event(ExceptionEvent(event, grouped[(priority, pub_id)][_i], result))
                continue
            if not return_result:
                continue
            if result.__class__ is Force:
                return result.value  # type: ignore
            if isinstance(result, Result):
                return Result.check_result(event, result)
            return Result.check_result(event, Result(result))


async def run_handler(
    target: Callable,
    event: Any,
    external_gather: Callable[[Any, Contexts], Awaitable[Contexts | None]] | None = None,
):
    contexts = await generate_contexts(event, external_gather)
    _target = Subscriber(target, providers=get_providers(event.__class__))
    return await _target.handle(contexts)


class _EventSystem:
    ref_tasks: set[asyncio.Task] = set()
    loop: asyncio.AbstractEventLoop | None = None

    @classmethod
    def add_task(cls, coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        loop = cls.loop or asyncio.get_running_loop()
        task = loop.create_task(coro)
        cls.ref_tasks.add(task)
        task.add_done_callback(cls.ref_tasks.discard)
        return task


def set_event_loop(loop: asyncio.AbstractEventLoop):
    _EventSystem.loop = loop


@atexit.register
def _cleanup():
    for task in _EventSystem.ref_tasks:
        if not task.done():
            task.cancel()
    _EventSystem.ref_tasks.clear()


def setup_fetch():
    _EventSystem.add_task(_loop_fetch())


async def _loop_fetch():
    while True:
        for publisher in _publishers.values():
            if not (event := (await publisher.supply())):
                continue
            publish(event)
        await asyncio.sleep(0.05)


def publish(event: Any, scope: str | Scope | None = None, inherit_ctx: Contexts | None = None):
    """发布事件"""
    if isinstance(scope, str) and ((sp := _scopes.get(scope)) and sp.available):
        coro = dispatch(sp.subscribers.values(), event, inherit_ctx)
    elif isinstance(scope, Scope) and scope.available:
        coro = dispatch(scope.subscribers.values(), event, inherit_ctx)
    else:
        scopes = [sp for sp in _scopes.values() if sp.available]
        coro = dispatch(chain.from_iterable(sp.subscribers.values() for sp in scopes), event, inherit_ctx)
    return _EventSystem.add_task(coro)


@overload
def post(event: Resultable[T], scope: str | Scope | None = None, inherit_ctx: Contexts | None = None) -> asyncio.Task[Result[T] | None]: ...


@overload
def post(event: Any, scope: str | Scope | None = None, inherit_ctx: Contexts | None = None) -> asyncio.Task[Result[Any] | None]: ...


def post(event: Any, scope: str | Scope | None = None, inherit_ctx: Contexts | None = None):
    """发布事件并返回第一个响应结果"""
    if isinstance(scope, str) and ((sp := _scopes.get(scope)) and sp.available):
        coro = dispatch(sp.subscribers.values(), event, inherit_ctx, return_result=True)
    elif isinstance(scope, Scope) and scope.available:
        coro = dispatch(scope.subscribers.values(), event, inherit_ctx, return_result=True)
    else:
        scopes = [sp for sp in _scopes.values() if sp.available]
        coro = dispatch(chain.from_iterable(sp.subscribers.values() for sp in scopes), event, inherit_ctx, return_result=True)
    return _EventSystem.add_task(coro)


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


def scope(id_: str | None = None):
    sp = Scope(id_)
    _scopes[sp.id] = sp
    return sp
