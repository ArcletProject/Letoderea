from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Iterable
from dataclasses import dataclass
from itertools import chain
from typing import Any, Callable, Literal, overload

from .event import EVENT
from .exceptions import PropagationCancelled
from .provider import get_providers, provide
from .publisher import search_publisher
from .subscriber import Subscriber, STOP
from .typing import Contexts, Force, Result


@dataclass(frozen=True)
class ExceptionEvent:
    origin: Any
    subscriber: Subscriber
    exception: BaseException

    async def gather(self, context: Contexts):
        context["exception"] = self.exception
        context["origin"] = self.origin
        context["subscriber"] = self.subscriber

    __publisher__ = "internal/exception"
    providers = [provide(Exception, "exception", validate=lambda p: issubclass(p.annotation, BaseException))]


async def publish_exc_event(event: ExceptionEvent):
    from .scope import _scopes

    pub_id = search_publisher(event).id
    if pub_id == "$backend":
        return
    scopes = [sp for sp in _scopes.values() if sp.available]
    await dispatch(chain.from_iterable(sp.iter_subscribers(pub_id) for sp in scopes), event)


@overload
async def dispatch(
    subscribers: Iterable[Subscriber],
    event: Any,
    *,
    external_gather: Callable[[Any], Awaitable[Contexts]] | None = None,
) -> None: ...


@overload
async def dispatch(
    subscribers: Iterable[Subscriber],
    event: Any,
    *,
    return_result: Literal[True],
    external_gather: Callable[[Any], Awaitable[Contexts]] | None = None,
) -> Result | None: ...


async def dispatch(
    subscribers: Iterable[Subscriber],
    event: Any,
    *,
    return_result: bool = False,
    external_gather: Callable[[Any], Awaitable[Contexts]] | None = None,
):
    if not subscribers:
        return
    contexts = await generate_contexts(event, external_gather)
    grouped: dict[int, list[Subscriber]] = {}
    for s in subscribers:
        if (priority := s.priority) not in grouped:
            grouped[priority] = []
        grouped[priority].append(s)
    for priority in sorted(grouped.keys()):
        tasks = [subscriber.handle(contexts.copy()) for subscriber in grouped[priority]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for _i, result in enumerate(results):
            if result is None or result is STOP:
                continue
            if result.__class__ is PropagationCancelled:
                return
            if isinstance(result, Exception):
                await publish_exc_event(ExceptionEvent(event, grouped[priority][_i], result))
                continue
            if not return_result:
                continue
            if result.__class__ is Force:
                return result.value  # type: ignore
            if isinstance(result, Result):
                return Result.check_result(event, result)
            return Result.check_result(event, Result(result))


async def generate_contexts(
    event: Any, external_gather: Callable[[Any], Awaitable[Contexts]] | None = None
) -> Contexts:
    if external_gather:
        contexts = await external_gather(event)
    else:
        contexts: Contexts = {EVENT: event}  # type: ignore
        await event.gather(contexts)
    return contexts


async def run_handler(
    target: Callable,
    event: Any,
    external_gather: Callable[[Any], Awaitable[Contexts]] | None = None,
):
    contexts = await generate_contexts(event, external_gather)
    _target = Subscriber(target, providers=get_providers(event.__class__))
    return await _target.handle(contexts)
