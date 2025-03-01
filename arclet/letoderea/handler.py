from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Iterable
from dataclasses import dataclass
from itertools import chain
from typing import Any, Callable, Literal, overload, Mapping

from .exceptions import STOP, BLOCK
from .provider import get_providers, provide
from .publisher import search_publisher
from .subscriber import Subscriber
from .typing import EVENT, Contexts, Force, Result


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
    providers = [
        provide(
            BaseException,
            "exception",
            validate=lambda p: (p.annotation and issubclass(p.annotation, BaseException)) or p.name == "exception"
        )
    ]


async def publish_exc_event(event: ExceptionEvent):
    from .scope import _scopes

    scopes = [sp for sp in _scopes.values() if sp.available]
    await dispatch(chain.from_iterable(sp.iter_subscribers(search_publisher(event), pass_backend=False) for sp in scopes), event)


@overload
async def dispatch(
    subscribers: Iterable[Subscriber],
    event: Any,
    gather: Callable[[Any], Awaitable[Mapping[str, Any]]] | None = None,
    *,
    inherit_ctx: Contexts | None = None,
) -> None: ...


@overload
async def dispatch(
    subscribers: Iterable[Subscriber],
    event: Any,
    gather: Callable[[Any], Awaitable[Mapping[str, Any]]] | None = None,
    *,
    return_result: Literal[True],
    inherit_ctx: Contexts | None = None,
) -> Result | None: ...


async def dispatch(
    subscribers: Iterable[Subscriber],
    event: Any,
    gather: Callable[[Any], Awaitable[Mapping[str, Any]]] | None = None,
    *,
    return_result: bool = False,
    inherit_ctx: Contexts | None = None,
):
    if not subscribers:
        return
    contexts = await generate_contexts(event, gather, inherit_ctx)
    grouped: dict[int, list[Subscriber]] = {}
    for s in subscribers:
        if (priority := s.priority) not in grouped:
            grouped[priority] = []
        grouped[priority].append(s)
    for priority in sorted(grouped.keys()):
        tasks = [subscriber.handle(contexts.copy()) for subscriber in grouped[priority]]
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
    event: Any, gather: Callable[[Any], Awaitable[Mapping[str, Any]]] | None = None, inherit_ctx: Contexts | None = None
) -> Contexts:
    contexts: Contexts = {EVENT: event}  # type: ignore
    if gather:
        contexts.update(await gather(event))
    elif hasattr(event, "gather"):
        await event.gather(contexts)
    elif hasattr(event, "__context_gather__"):
        contexts.update(await event.__context_gather__())
    if inherit_ctx:
        inherit_ctx.update(contexts)
        return inherit_ctx
    return contexts


async def run_handler(
    target: Callable,
    event: Any,
    external_gather: Callable[[Any], Awaitable[Contexts]] | None = None,
):
    contexts = await generate_contexts(event, external_gather)
    _target = Subscriber(target, providers=get_providers(event.__class__))
    return await _target.handle(contexts)
