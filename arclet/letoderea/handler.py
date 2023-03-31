from __future__ import annotations

import inspect
import pprint
import sys
import traceback
from typing import Any, Callable, Type, cast
from tarina import Empty, generic_isinstance, run_always_await

from .auxiliary import Executor
from .event import BaseEvent, get_providers
from .exceptions import (
    JudgementError,
    ParsingStop,
    PropagationCancelled,
    UndefinedRequirement,
    UnexpectedArgument,
)
from .provider import Provider, provide
from .subscriber import Subscriber
from .typing import Contexts, Force


async def depend_handler(
    target: Subscriber | Callable,
    event: BaseEvent,
):
    if target.__class__ != Subscriber:
        target = Subscriber(target, providers=get_providers(event))
    contexts = cast(Contexts, {"event": event, "$subscriber": target})
    await event.gather(contexts)
    try:
        if "prepare" in target.auxiliaries:
            for aux in target.auxiliaries["prepare"]:
                await prepare(aux, contexts)
        arguments = cast(Contexts, {})
        for param in target.params:
            if param.depend:
                arguments[param.name] = await param.depend(contexts)
            else:
                arguments[param.name] = await param_parser(
                    param.name,
                    param.annotation,
                    param.default,
                    param.providers,
                    contexts,
                )
        if "complete" in target.auxiliaries:
            for aux in target.auxiliaries["complete"]:
                await complete(aux, arguments)
        result = await run_always_await(target.callable_target, **arguments)
    except UndefinedRequirement as u:
        name, *_, pds = u.args
        param = inspect.signature(target.callable_target).parameters[name]
        code = target.callable_target.__code__  # type: ignore
        etype: Type[Exception] = type(  # type: ignore
            "UndefinedRequirement",
            (UndefinedRequirement, SyntaxError),
            {},
        )
        _args = (code.co_filename, code.co_firstlineno, 1, str(param))
        if sys.version_info >= (3, 10):
            _args += (code.co_firstlineno, len(name) + 1)
        traceback.print_exception(
            etype,
            etype(
                f"\nUnable to parse parameter ({param}) "
                f"\n by providers"
                f"\n{pprint.pformat(pds)}"
                f"\n with context"
                f"\n{pprint.pformat(contexts)}",
                _args,
            ),
            u.__traceback__,
        )
        raise
    except (ParsingStop, PropagationCancelled, JudgementError, UnexpectedArgument):
        raise
    except Exception as e:
        traceback.print_exc()
        raise e
    finally:
        if "cleanup" in target.auxiliaries:
            for aux in target.auxiliaries["cleanup"]:
                await aux("cleanup", contexts)
        contexts.clear()
    return result


async def prepare(decorator: Executor, ctx: Contexts):
    res = await decorator("prepare", ctx.copy())  # type: ignore
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
    res = await decorator("complete", ctx.copy())  # type: ignore
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


async def param_parser(
    name: str,
    annotation: Any,
    default: Any,
    providers: list[Provider],
    context: Contexts | dict[str, Any],
):
    """
    将调用函数提供的参数字典与事件提供的参数字典进行比对，并返回正确的参数字典

    Args:
        name: 参数名
        annotation: 参数类型
        default: 默认值
        providers: 参数提供者列表
        context: 函数可返回的参数字典
    Returns:
        函数需要的参数字典
    """
    if name in context:
        return context[name]
    for _provider in providers:
        res = await _provider(context)  # type: ignore
        if res is None:
            continue
        if res.__class__ is Force:
            res = res.value
        return res
    if annotation:
        for key, value in context.items():
            if generic_isinstance(value, annotation):
                providers.append(provide(annotation, target=key)())
                return value
            if isinstance(annotation, str) and f"{type(value)}" == annotation:
                providers.append(provide(type(value), target=key)())
                return value
    if default is not Empty:
        return default
    raise UndefinedRequirement(name, annotation, default, providers)
