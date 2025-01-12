from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any, Awaitable, Callable, Literal, overload

from .event import EVENT
from .exceptions import PropagationCancelled
from .provider import get_providers
from .subscriber import Subscriber
from .typing import Contexts, Result


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
) -> Result[Any] | None: ...


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
            if result.__class__ is PropagationCancelled:
                return
            if not return_result:
                continue
            if isinstance(result, Result):
                return Result.check_result(event, result)
            if not isinstance(result, BaseException) and result is not None and result is not False:
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
