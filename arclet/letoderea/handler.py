from __future__ import annotations

import asyncio
import inspect
import pprint
import sys
import traceback
from typing import Callable, Type

from tarina import group_dict

from .auxiliary import Cleanup, Complete, Executor, Prepare
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
from .typing import Contexts


async def dispatch(subscribers: list[Subscriber], event: BaseEvent):
    if not subscribers:
        return
    grouped: dict[int, list[Subscriber]] = group_dict(subscribers, lambda x: x.priority)
    for _, current_subs in sorted(grouped.items(), key=lambda x: x[0]):
        tasks = [depend_handler(subscriber, event) for subscriber in current_subs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if result.__class__ is PropagationCancelled:
                return


def exception_handler(e: Exception, target: Subscriber, contexts: Contexts, inner: bool = False):
    if isinstance(e, UndefinedRequirement) and not isinstance(e, SyntaxError):
        name, *_, pds = e.args
        param = inspect.signature(target.callable_target).parameters[name]
        code = target.callable_target.__code__  # type: ignore
        etype: Type[Exception] = type(  # type: ignore
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
            f"\nUnable to parse parameter ({param}) "
            f"\n--------------------------------------------------"
            f"\nproviders on parameter:"
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
    target: Subscriber | Callable, event: BaseEvent | None = None, source: Contexts | None = None, inner: bool = False
):
    if event:
        if target.__class__ != Subscriber:
            target = Subscriber(target, providers=get_providers(source))  # type: ignore
        contexts: Contexts = {"$event": source, "$subscriber": target}  # type: ignore
        await event.gather(contexts)
    elif source:
        contexts = source
        if target.__class__ != Subscriber:
            target = Subscriber(target, providers=get_providers(source["$event"]))  # type: ignore
        contexts["$subscriber"] = target
    else:
        raise ValueError("Empty source")
    try:
        if Prepare in target.auxiliaries:
            for aux in target.auxiliaries[Prepare]:
                await prepare(aux, contexts)
        arguments: Contexts = {}  # type: ignore
        for param in target.params:
            arguments[param.name] = await param.solve(contexts)
        if Complete in target.auxiliaries:
            for aux in target.auxiliaries[Complete]:
                await complete(aux, arguments)
        result = await target.callable_target(**arguments)
    except InnerHandlerException as e:
        if inner:
            raise
        raise exception_handler(e.args[0], target, contexts) from e  # type: ignore
    except Exception as e:
        raise exception_handler(e, target, contexts, inner) from e  # type: ignore
    finally:
        if Cleanup in target.auxiliaries:
            for aux in target.auxiliaries[Cleanup]:
                await aux(Cleanup, contexts)
        contexts.clear()
    return result


async def prepare(decorator: Executor, ctx: Contexts):
    res = await decorator(Prepare, ctx.copy())  # type: ignore
    if res is False:
        raise JudgementError
    if isinstance(res, dict):
        ctx.update(res)


async def complete(decorator: Executor, ctx: Contexts):
    """
    在解析前执行的操作

    Args:
        decorator: 解析器列表
        ctx: 事件参数字典
    """
    keys = set(ctx.keys())
    res = await decorator(Complete, ctx.copy())  # type: ignore
    if res is False:
        raise JudgementError
    if isinstance(res, dict):
        if set(res.keys()) == keys:
            ctx.clear()
            ctx.update(res)
            return
        if len(keys) > len(res):
            raise UnexpectedArgument(f"Missing requirement in {keys - set(res.keys())}")
        if len(keys) < len(res):
            raise UnexpectedArgument(f"Unexpected argument in {keys - set(res.keys())}")
