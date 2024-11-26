from __future__ import annotations

import asyncio
import inspect
import pprint
import sys
import traceback
from typing import Literal, Callable, overload, Any
from collections.abc import Iterable

from .auxiliary import Interface, Cleanup, Complete, Prepare, OnError, prepare, cleanup, complete, onerror
from .event import BaseEvent, get_providers
from .exceptions import (
    InnerHandlerException,
    JudgementError,
    ParsingStop,
    PropagationCancelled,
    UndefinedRequirement,
    UnexpectedArgument,
)
from .subscriber import Subscriber
from .typing import Contexts, Result


@overload
async def dispatch(subscribers: Iterable[Subscriber], event: BaseEvent) -> None:
    ...


@overload
async def dispatch(subscribers: Iterable[Subscriber], event: BaseEvent, return_result: Literal[True]) -> Result | None:
    ...


async def dispatch(subscribers: Iterable[Subscriber], event: BaseEvent, return_result: bool = False):
    if not subscribers:
        return
    grouped: dict[int, list[Subscriber]] = {}
    for s in subscribers:
        grouped.setdefault(s.priority, []).append(s)
    for priority in sorted(grouped.keys()):
        tasks = [depend_handler(subscriber, event) for subscriber in grouped[priority]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if result.__class__ is PropagationCancelled:
                return
            if not return_result:
                continue
            if isinstance(result, Result):
                return result
            if not isinstance(result, BaseException) and result is not None and result is not False:
                return Result(result)


def exception_handler(e: Exception, target: Subscriber, contexts: Contexts, inner: bool = False):
    if isinstance(e, UndefinedRequirement) and not isinstance(e, SyntaxError):
        name, *_, pds = e.args
        param = inspect.signature(target.callable_target).parameters[name]
        code = target.callable_target.__code__  # type: ignore
        etype: type[Exception] = type(  # type: ignore
            "UndefinedRequirement",
            (
                UndefinedRequirement,
                SyntaxError,
            ),
            {},
        )
        _args = (code.co_filename, code.co_firstlineno, 1, str(param))
        if sys.version_info >= (3, 10):
            _args += (code.co_firstlineno, len(name) + 1)
        exc: SyntaxError = etype(
            f"Unable to parse parameter ({param})"
            f"\n--------------------------------------------------"
            f"\nproviders on parameter ({param}):"
            f"\n{pprint.pformat(pds)}"
            f"\n--------------------------------------------------"
            f"\ncurrent context"
            f"\n{pprint.pformat(contexts)}",
            _args,
        )
        exc.__traceback__ = e.__traceback__
        if inner:
            return InnerHandlerException(exc)
        traceback.print_exception(
            etype,
            exc,
            e.__traceback__,
        )
        return exc
    if isinstance(
        e,
        (
            ParsingStop,
            PropagationCancelled,
            JudgementError,
            UnexpectedArgument,
            InnerHandlerException,
        ),
    ):
        return InnerHandlerException(e) if inner else e
    if inner:
        return InnerHandlerException(e)
    traceback.print_exception(e.__class__, e, e.__traceback__)
    return e


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
    try:
        if Prepare in _target.auxiliaries:
            interface = Interface(contexts, _target.providers)
            await prepare(_target.auxiliaries[Prepare], interface)
        arguments: Contexts = {}  # type: ignore
        for param in _target.params:
            if param.depend:
                arguments[param.name] = await depend_handler(param.depend.sub, source=contexts, inner=True)
            else:
                arguments[param.name] = await param.solve(contexts)
        if Complete in _target.auxiliaries:
            interface = Interface(arguments, _target.providers)
            await complete(_target.auxiliaries[Complete], interface)
        result = await _target.callable_target(**arguments)
    except InnerHandlerException as e:
        if inner:
            raise
        raise exception_handler(e.args[0], _target, contexts) from e  # type: ignore
    except Exception as e:
        raise exception_handler(e, _target, contexts, inner) from e  # type: ignore
    finally:
        _, exception, tb = sys.exc_info()
        if exception and OnError in _target.auxiliaries:
            contexts["$error"] = exception
            interface = Interface(contexts, _target.providers)
            await onerror(_target.auxiliaries[OnError], interface)
    if Cleanup in _target.auxiliaries:
        contexts["$result"] = result
        interface = Interface(contexts, _target.providers)
        await cleanup(_target.auxiliaries[Cleanup], interface)
    contexts.clear()
    return result
