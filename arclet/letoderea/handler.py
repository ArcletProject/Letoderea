from __future__ import annotations

import asyncio
from collections.abc import Iterable
from itertools import chain
from typing import Any, Callable, Literal, overload
from collections.abc import Awaitable

from .event import EVENT, ExceptionEvent
from .exceptions import PropagationCancelled, HandlerStop
from .provider import get_providers
from .publisher import search_publisher
from .subscriber import Subscriber
from .typing import Contexts, Result


async def publish_exc_event(origin: Any, exception: Exception):
    from .scope import _scopes

    event = ExceptionEvent(origin, exception)
    pub_id = search_publisher(event).id
    scopes = [sp for sp in _scopes.values() if sp.available]
    await dispatch(
        chain.from_iterable(sp.iter_subscribers(pub_id) for sp in scopes),
        event,
    )


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
        for result in results:
            if result is None:
                continue
            if result.__class__ is PropagationCancelled:
                return
            if isinstance(result, Exception):
                if not isinstance(result, HandlerStop):
                    await publish_exc_event(event, result)
                continue
            if not return_result:
                continue
            if isinstance(result, Result):
                return Result.check_result(event, result)
            if result is not False:
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
