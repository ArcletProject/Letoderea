from __future__ import annotations
import traceback
from typing import Any, Callable

from .provider import Provider
from .subscriber import Subscriber
from .event import BaseEvent, get_providers
from .exceptions import (
    UndefinedRequirement,
    UnexpectedArgument,
    ParsingStop,
    PropagationCancelled,
    JudgementError,
)
from .utils import run_always_await
from .typing import Empty, Contexts, Force
from .auxiliary import BaseAuxiliary, Scope, AuxType
from .context import event_ctx


async def depend_handler(
    target: Subscriber | Callable,
    event: BaseEvent,
):
    if target.__class__ != Subscriber:
        target = Subscriber(target, providers=get_providers(event))
    contexts = {"event": event, "$subscriber": target}
    await event.gather(contexts)
    try:
        for aux in target.auxiliaries:
            await before_parse(aux, contexts)
        arguments = await param_parser(target.params, contexts, target.revise_mapping)

        for aux in target.auxiliaries:
            await after_parse(aux, arguments)
        result = await run_always_await(target.callable_target, **arguments)
        for aux in target.auxiliaries:
            await execution_complete(aux)
    except (UnexpectedArgument, UndefinedRequirement):
        traceback.print_exc()
        raise
    except (ParsingStop, PropagationCancelled, JudgementError):
        raise
    except Exception as e:
        traceback.print_exc()
        raise e
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
                raise UndefinedRequirement(
                    f"Undefined requirement in {set(data.keys()) - set(data.keys())}"
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
    params: list[tuple[str, Any, Any, list[Provider]]],
    context: Contexts,
    revise: dict[str, Any],
):
    """
    将调用函数提供的参数字典与事件提供的参数字典进行比对，并返回正确的参数字典

    Args:
        params: 调用的函数的参数列表
        context: 函数可返回的参数字典
        revise: 修正的参数字典
    Returns:
        函数需要的参数字典
    """
    arguments_dict = {}
    for name, annotation, default, providers in params:
        if name in revise:
            name = revise[name]
        if name in context:
            arguments_dict[name] = context[name]
        else:
            for provider in providers:
                res = await provider(context)
                if res is not None:
                    if res.__class__ is Force:
                        res = res.value
                    arguments_dict[name] = res
                    break
        if name not in arguments_dict and default is not Empty:
            arguments_dict[name] = default
        if isinstance(default, BaseAuxiliary):
            aux = default.handlers.get(Scope.parsing)
            if not aux:
                continue
            for handler in filter(
                lambda x: x.aux_type == AuxType.supply, aux
            ):
                res = await handler.supply(default, context)
                if res is None:
                    continue
                if res.__class__ is Force:
                    res = res.value
                arguments_dict[name] = res
                break
        if name not in arguments_dict:
            # TODO: 遍历 context，如果有符合的类型，就直接返回
            raise UnexpectedArgument(
                f"argument: {name} ({annotation}) without value"
            )
    return arguments_dict
