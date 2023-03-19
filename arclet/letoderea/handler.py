from __future__ import annotations
import traceback
import asyncio
from itertools import chain
from inspect import isclass
from typing import Tuple, Dict, Any, Union, Callable, List, get_args

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
from .utils import argument_analysis, run_always_await
from .typing import Empty, Contexts, Force
from .auxiliary import BaseAuxiliary
from .context import event_ctx


async def depend_handler(
    target: Subscriber | Callable,
    event: BaseEvent,
):
    if not isinstance(target, Subscriber):
        target = Subscriber(target, providers=get_providers(event))
    collection = {"event": event}
    await event.gather(collection)
    try:
        # for aux in target.auxiliaries:
        #     await before_parse(aux, event_data)
        arguments = await param_parser(target.params, collection, target.revise_mapping)

        # for aux in auxiliaries:
        #     await after_parse(aux, arguments)
        result = await run_always_await(target.callable_target, **arguments)
        # for aux in auxiliaries:
        #     await execution_complete(aux)
    except (UnexpectedArgument, UndefinedRequirement):
        traceback.print_exc()
        raise
    except (ParsingStop, PropagationCancelled, JudgementError):
        raise
    except Exception as e:
        traceback.print_exc()
        raise e
    return result

#
# async def before_parse(
#     decorator: BaseAuxiliary,
#     event_data: Dict[type, Dict[str, Any]],
# ):
#     """
#     在解析前执行的操作
#
#     Args:
#         decorator: 解析器列表
#         event_data: 事件参数字典
#     """
#     if not decorator.aux_handlers.get("before_parse"):
#         return
#     for handler in decorator.aux_handlers["before_parse"]:
#         if handler.aux_type == "judge":
#             await handler.judge_wrapper(decorator, event_ctx.get())
#         if handler.aux_type == "supply":
#             for k, v in event_data.copy().items():
#                 if handler.keep:
#                     event_data.update(
#                         await handler.supply_wrapper_keep(decorator, k, v)
#                     )
#                 else:
#                     event_data[k].update(await handler.supply_wrapper(decorator, k, v))
#
#
# async def after_parse(
#     decorator: BaseAuxiliary,
#     event_data: Dict[str, Any],
# ):
#     """
#     在解析前执行的操作
#
#     Args:
#         decorator: 解析器列表
#         event_data: 事件参数字典
#     """
#     if not decorator.aux_handlers.get("after_parse"):
#         return
#     for handler in decorator.aux_handlers["after_parse"]:
#         if handler.aux_type == "supply":
#             for k, v in event_data.copy().items():
#                 if handler.keep:
#                     r = await handler.supply_wrapper_keep(decorator, type(v), {k: v})
#                     event_data.update(r.popitem()[1])
#                 else:
#                     event_data[k].update(
#                         await handler.supply_wrapper(decorator, type(v), {k: v})
#                     )
#
#
# async def execution_complete(
#     decorator: BaseAuxiliary,
# ):
#     """
#     在解析前执行的操作
#
#     Args:
#         decorator: 解析器列表
#     """
#     if not decorator.aux_handlers.get("execution_complete"):
#         return
#     for handler in decorator.aux_handlers["execution_complete"]:
#         if handler.aux_type == "judge":
#             await handler.judge_wrapper(decorator, event_ctx.get())
#


async def param_parser(
    params: dict[str, tuple[Any, Any, list[Provider]]],
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
    for name, slot in params.items():
        annotation, default, providers = slot
        if name in revise:
            name = revise[name]
        if name in context:
            arguments_dict[name] = context[name]
            continue

        for provider in providers:
            res = await provider(context)
            if res is not None:
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
