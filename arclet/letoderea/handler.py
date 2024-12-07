from __future__ import annotations

import asyncio
from typing import Literal, Callable, overload, Any
from collections.abc import Iterable

from tarina import generic_isinstance

from .event import get_providers
from .exceptions import (
    PropagationCancelled,
)
from .subscriber import Subscriber
from .typing import Contexts, Result


def _check_result(event: Any, result: Result):
    if not hasattr(event, "__result_type__"):
        return result
    if generic_isinstance(result.value, event.__result_type__):
        return result
    return


@overload
async def dispatch(subscribers: Iterable[Subscriber], event: Any) -> None:
    ...


@overload
async def dispatch(subscribers: Iterable[Subscriber], event: Any, return_result: Literal[True]) -> Result | None:
    ...


async def dispatch(subscribers: Iterable[Subscriber], event: Any, return_result: bool = False):
    if not subscribers:
        return
    grouped: dict[int, list[Subscriber]] = {}
    for s in subscribers:
        if (priority := s.priority) not in grouped:
            grouped[priority] = []
        grouped[priority].append(s)
    for priority in sorted(grouped.keys()):
        tasks = [depend_handler(subscriber, event) for subscriber in grouped[priority]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if result.__class__ is PropagationCancelled:
                return
            if not return_result:
                continue
            if isinstance(result, Result):
                return _check_result(event, result)
            if not isinstance(result, BaseException) and result is not None and result is not False:
                return _check_result(event, Result(result))


async def depend_handler(
    target: Subscriber | Callable,
    event: Any | None = None,
    source: Contexts | None = None,
    inner: bool = False,
):
    if event:
        if target.__class__ != Subscriber:
            _target = Subscriber(target, providers=get_providers(event.__class__))  # type: ignore
        else:
            _target: Subscriber = target  # type: ignore
        if _target.external_gather:
            contexts = await _target.external_gather(event)
            contexts["$subscriber"] = _target
        else:
            contexts: Contexts = {"$event": event, "$subscriber": _target}  # type: ignore
            await event.gather(contexts)
    elif source:
        contexts = source
        if target.__class__ != Subscriber:
            _target = Subscriber(target, providers=get_providers(source["$event"].__class__))  # type: ignore
        else:
            _target: Subscriber = target  # type: ignore
        contexts["$subscriber"] = _target
    else:
        raise ValueError("Empty source")
    return await _target.handle(contexts, inner=inner)
