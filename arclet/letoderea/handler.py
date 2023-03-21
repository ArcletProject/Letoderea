from __future__ import annotations

import inspect
import pprint
import sys
import traceback
from typing import Any, Callable, cast, Type

from .provider import Provider, provider
from .subscriber import Subscriber
from .event import BaseEvent, get_providers
from .exceptions import (
    UndefinedRequirement,
    UnexpectedArgument,
    ParsingStop,
    PropagationCancelled,
    JudgementError,
)
from .utils import run_always_await, Force
from .typing import Empty, Contexts, generic_isinstance
from .auxiliary import BaseAuxiliary, Scope, AuxType
from .context import event_ctx


async def depend_handler(
    target: Subscriber | Callable,
    event: BaseEvent,
):
    if target.__class__ != Subscriber:
        target = Subscriber(target, providers=get_providers(event))
    contexts = cast(Contexts, {"event": event, "$subscriber": target})
    await event.gather(contexts)
    try:
        for aux in target.auxiliaries:
            await before_parse(aux, contexts)
        arguments = cast(Contexts, {})
        for param in target.params:
            if param.depend:
                arguments[param.name] = await param.depend(contexts)
            else:
                arguments[param.name] = await param_parser(
                    param.name, param.annotation, param.default, param.providers, contexts
                )
        for aux in target.auxiliaries:
            await after_parse(aux, arguments)
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
        for aux in target.auxiliaries:
            await execution_complete(aux)
    return result


async def before_parse(
    decorator: BaseAuxiliary,
    contexts: Contexts,
):
    """
    在解析前执行的操作

    Args:
        decorator: 解析器列表
        contexts: 事件参数字典
    """
    if not decorator.handlers.get(Scope.before_parse):
        return
    for handler in decorator.handlers[Scope.before_parse]:
        if handler.aux_type == AuxType.judge:
            await handler.judge(decorator, contexts["event"])
        else:
            await handler.supply(decorator, contexts)


async def after_parse(
    decorator: BaseAuxiliary,
    data: Contexts,
):
    """
    在解析前执行的操作

    Args:
        decorator: 解析器列表
        data: 事件参数字典
    """
    if not decorator.handlers.get(Scope.after_parse):
        return
    for handler in decorator.handlers[Scope.after_parse]:
        if handler.aux_type == AuxType.judge:
            await handler.judge(decorator, data["event"])
        else:
            length = len(data)
            await handler.supply(decorator, data)
            if length > len(data):
                raise UnexpectedArgument(
                    f"Missing requirement in {set(data.keys()) - set(data.keys())}"
                )
            if length < len(data):
                raise UnexpectedArgument(
                    f"Unexpected argument in {set(data.keys()) - set(data.keys())}"
                )


async def execution_complete(decorator: BaseAuxiliary):
    """
    在解析前执行的操作

    Args:
        decorator: 解析器列表
    """
    if not decorator.handlers.get(Scope.cleanup):
        return
    for handler in decorator.handlers[Scope.cleanup]:
        if handler.aux_type == AuxType.judge:
            await handler.judge(decorator, event_ctx.get())


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
                providers.append(provider(annotation, target=key)())
                return value
            if isinstance(annotation, str) and f"{type(value)}" == annotation:
                providers.append(provider(type(value), target=key)())
                return value
    if default is not Empty:
        return default
    raise UndefinedRequirement(
        name, annotation, default, providers
    )
