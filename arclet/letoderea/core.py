from __future__ import annotations

import asyncio
import atexit
from collections import defaultdict
from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine, Iterable
from dataclasses import dataclass
from itertools import chain
from operator import attrgetter
from types import AsyncGeneratorType
from typing import Any, TypeVar, cast, overload
from typing_extensions import dataclass_transform

from .context import Contexts, generate_contexts
from .exceptions import BLOCK, STOP, _ExitException
from .provider import get_providers, provide
from .publisher import Publisher, _publishers, define, gather, get_publishers
from .scope import Scope, SubscriberSlot, _scopes, on, use  # noqa: F401
from .subscriber import Subscriber
from .typing import Force, Result, Resultable

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

    async def gather(self, context: Contexts):
        return context.update(exception=self.exception, origin=self.origin, subscriber=self.subscriber)


exc_pub = define(ExceptionEvent, name="internal/exception")


def publish_exc_event(event: ExceptionEvent):
    if isinstance(event.origin, ExceptionEvent) or isinstance(event.exception, _ExitException):  # pragma: no cover
        return
    scopes = [sp for sp in _scopes.values() if sp.available]
    subs = [slot for sp in scopes for slot in sp.subscribers if slot.publisher_id != "$backend"]
    return add_task(dispatch(event, slots=subs))


async def compute(event: Any, scope: str | Scope | None = None, slots: Iterable[SubscriberSlot] | None = None, inherit_ctx: Contexts | None = None):
    """准备事件处理的公共逻辑"""
    if slots:
        pass
    elif isinstance(scope, str) and ((sp := _scopes.get(scope)) and sp.available):
        slots = sp.subscribers
    elif isinstance(scope, Scope) and scope.available:
        slots = scope.subscribers
    else:
        slots = chain.from_iterable(sp.subscribers for sp in _scopes.values() if sp.available)

    context_map: dict[str, Contexts] = {}

    pubs = get_publishers(event)
    grouped = defaultdict(list)

    for slot in sorted(slots, key=attrgetter("priority")):
        pub_id = slot.publisher_id
        if pub_id != "$backend" and pub_id not in pubs:
            continue
        if pub_id not in context_map:
            context_map[pub_id] = await generate_contexts(event, None if pub_id == "$backend" else pubs[pub_id].supplier, inherit_ctx)
        grouped[(slot.priority, pub_id)].append(slot.subscriber)

    return grouped, context_map


async def dispatch(event: Any, scope: str | Scope | None = None, slots: Iterable[SubscriberSlot] | None = None, inherit_ctx: Contexts | None = None):
    grouped, context_map = await compute(event, scope, slots, inherit_ctx)

    for key, subs in grouped.items():
        contexts = context_map[key[1]]
        tasks = [subscriber.handle(contexts.copy()) for subscriber in subs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for _i, result in enumerate(results):
            if result is None or result is STOP:
                continue
            if result is BLOCK:
                return
            if isinstance(result, BaseException):
                if isinstance(result, _ExitException) and result.args[1]:  # pragma: no cover
                    return
                publish_exc_event(ExceptionEvent(event, subs[_i], result))
            if isinstance(result, AsyncGeneratorType):  # pragma: no cover
                async for res in result:
                    if result is None or result is STOP:
                        continue
                    if res is BLOCK:
                        return
                    if isinstance(res, _ExitException) and res.args[1]:
                        return


async def serial_exec(subs: list[Subscriber], ctx: Contexts):
    for subscriber in subs:
        try:
            yield subscriber, await subscriber.handle(ctx.copy())
        except BaseException as e:
            yield subscriber, e


async def serial_exec_concurrent(subs: list[Subscriber], ctx: Contexts):
    pending = {asyncio.create_task(subscriber.handle(ctx.copy()), name=f"sub_{i}") for i, subscriber in enumerate(subs)}
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            subscriber = subs[int(task.get_name().split("_")[1])]
            try:
                yield subscriber, await task
            except GeneratorExit:
                if pending:
                    for t in pending:
                        t.cancel()  # 发送取消信号
                    await asyncio.gather(*pending, return_exceptions=True)
                raise
            except BaseException as e:  # pragma: no cover
                yield subscriber, e


async def serial(event: Any, scope: str | Scope | None = None, slots: Iterable[SubscriberSlot] | None = None, inherit_ctx: Contexts | None = None):
    grouped, context_map = await compute(event, scope, slots, inherit_ctx)
    for key, subs in grouped.items():
        contexts = context_map[key[1]]
        gene = serial_exec_concurrent(subs, contexts)
        async for subscriber, result in gene:
            if result is None or result is STOP:
                continue
            if result is BLOCK:  # pragma: no cover
                return
            if isinstance(result, BaseException):  # pragma: no cover
                if isinstance(result, _ExitException):
                    return result.args[0]
                publish_exc_event(ExceptionEvent(event, subscriber, result))
            elif isinstance(result, AsyncGeneratorType):  # pragma: no cover
                async for res in result:
                    if res is None or res is STOP:
                        continue
                    if res is BLOCK:
                        return
                    if isinstance(res, _ExitException):
                        return res.args[0]
                    return res
            else:
                return result


async def broadcast(event: Any, scope: str | Scope | None = None, slots: Iterable[SubscriberSlot] | None = None, inherit_ctx: Contexts | None = None, concurrent: bool = False):  # pragma: no cover
    grouped, context_map = await compute(event, scope, slots, inherit_ctx)
    for key, subs in grouped.items():
        contexts = context_map[key[1]]
        gene = serial_exec_concurrent(subs, contexts) if concurrent else serial_exec(subs, contexts)
        async for subscriber, result in gene:
            if result is None or result is STOP:
                continue
            if result is BLOCK:
                return
            if isinstance(result, BaseException):
                if isinstance(result, _ExitException):
                    yield result.args[0]
                    if result.args[1]:
                        return
                    continue
                publish_exc_event(ExceptionEvent(event, subscriber, result))
            elif isinstance(result, AsyncGeneratorType):
                async for res in result:
                    if res is None or res is STOP:
                        continue
                    if res is BLOCK:
                        return
                    if isinstance(res, _ExitException):
                        yield res.args[0]
                        if res.args[1]:
                            return
                        continue
                    yield res
            else:
                yield result


async def _post(event: Any, scope: str | Scope | None = None, inherit_ctx: Contexts | None = None, *, validate: bool = False):
    res = await serial(event, scope, inherit_ctx=inherit_ctx)
    if res is None:
        return
    if res.__class__ is Force:  # pragma: no cover
        res = res.value
    if validate and hasattr(event, "check_result"):
        return cast(Resultable, event).check_result(res.value if isinstance(res, Result) else res)
    return res if isinstance(res, Result) else Result(res)


async def run_handler(
    target: Callable[..., T],
    event: Any,
    external_gather: Callable[[Any, Contexts], Awaitable[Contexts | None]] | None = None,
):
    contexts = await generate_contexts(event, external_gather)
    _target: Subscriber[T] = target if isinstance(target, Subscriber) else Subscriber(target, providers=get_providers(event.__class__))
    return await _target.handle(contexts)


class _EventSystem:
    ref_tasks: set[asyncio.Task] = set()
    loop: asyncio.AbstractEventLoop | None = None


def add_task(coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
    loop = _EventSystem.loop or asyncio.get_running_loop()
    task = loop.create_task(coro)
    _EventSystem.ref_tasks.add(task)
    task.add_done_callback(_EventSystem.ref_tasks.discard)
    return task


def set_event_loop(loop: asyncio.AbstractEventLoop):  # pragma: no cover
    _EventSystem.loop = loop


@atexit.register
def _cleanup():  # pragma: no cover
    for task in _EventSystem.ref_tasks:
        if not task.done() and not task.get_loop().is_closed():
            task.cancel()
    _EventSystem.ref_tasks.clear()


def setup_fetch():
    for pub in _publishers.values():
        add_task(_loop_fetch(pub))


async def _loop_fetch(publisher: Publisher):
    while True:
        if not (event := (await publisher.supply())):  # pragma: no cover
            await asyncio.sleep(0.05)
            continue
        await publish(event)
        await asyncio.sleep(0.05)


def publish(event: Any, scope: str | Scope | None = None, inherit_ctx: Contexts | None = None) -> asyncio.Task[None]:
    """发布事件，并行处理所有响应"""
    return add_task(dispatch(event, scope, inherit_ctx=inherit_ctx))


@overload
def post(event: Resultable[T], scope: str | Scope | None = None, inherit_ctx: Contexts | None = None, validate: bool = False) -> asyncio.Task[Result[T] | None]: ...
@overload
def post(event: Any, scope: str | Scope | None = None, inherit_ctx: Contexts | None = None, validate: bool = False) -> asyncio.Task[Result[Any] | None]: ...
def post(event: Any, scope: str | Scope | None = None, inherit_ctx: Contexts | None = None, validate: bool = False):
    """发布事件，并行处理所有响应并返回第一个响应结果"""
    return add_task(_post(event, scope, inherit_ctx=inherit_ctx, validate=validate))


@overload
def waterfall(event: Resultable[T], scope: str | Scope | None = None, inherit_ctx: Contexts | None = None, concurrent: bool = False) -> AsyncGenerator[Result[T], Any]: ...
@overload
def waterfall(event: Any, scope: str | Scope | None = None,  inherit_ctx: Contexts | None = None, concurrent: bool = False) -> AsyncGenerator[Result[Any], Any]: ...
async def waterfall(event: Any, scope: str | Scope | None = None, inherit_ctx: Contexts | None = None, concurrent: bool = False):  # pragma: no cover
    """发布事件，并行处理事件，逐个产出所有响应结果"""
    async for res in broadcast(event, scope, inherit_ctx=inherit_ctx, concurrent=concurrent):
        if res.__class__ is Force:
            res = res.value
        yield res if isinstance(res, Result) else Result(res)


C = TypeVar("C")


@overload
@dataclass_transform()
def make_event(cls: None, /) -> Callable[[type[C]], type[C]]: ...


@overload
@dataclass_transform()
def make_event(cls: type[C], /) -> type[C]: ...


@overload
@dataclass_transform()
def make_event(*, name: str | None = None, init: bool = True, repr: bool = True, eq: bool = True, order: bool = False, unsafe_hash: bool = False, frozen: bool = False) -> Callable[[type[C]], type[C]]: ...


@dataclass_transform()
def make_event(cls: type[C] | None = None, *, name: str | None = None, **kwargs) -> Callable[[type[C]], type[C]] | type[C]:

    def wrapper(_cls: type[C], /):
        _cls = dataclass(**kwargs)(_cls)
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

    if cls is None:
        return wrapper
    return wrapper(cls)


scope = Scope.of
