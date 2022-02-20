import traceback
from typing import Tuple, Dict, Any, Union, Callable, List, Optional
from .entities.subscriber import Subscriber
from .entities.event import TemplateEvent, ParamRet
from .exceptions import UndefinedRequirement, UnexpectedArgument, ParsingStop, PropagationCancelled, JudgementError
from .utils import argument_analysis, run_always_await, Empty, TEvent, ContextModel
from .entities.auxiliary import BaseAuxiliary

event_ctx: ContextModel[TemplateEvent] = ContextModel("leto::event")


async def await_exec_target(
        target: Union[Subscriber, Callable],
        events: Union[List[TEvent], ParamRet],
):
    is_subscriber = False
    if isinstance(target, Subscriber):
        is_subscriber = True
    auxiliaries = target.auxiliaries if is_subscriber else []
    callable_target = target.callable_target if is_subscriber else target
    event_data = target.internal_arguments if is_subscriber else {}
    revise = target.revise_dispatches if is_subscriber else {}
    target_param = target.params if is_subscriber else argument_analysis(callable_target)
    if isinstance(events, Dict):
        event_data.update(events)
    else:
        for event in events:
            event_data.update(event.get_params())

    try:
        for aux in auxiliaries:
            await before_parse(aux, event_data)
        arguments, fixed = await param_parser(target_param, event_data, revise)
        if is_subscriber:
            target.revise_dispatches = fixed
        for aux in auxiliaries:
            await after_parse(aux, arguments)
        result = await run_always_await(callable_target, **arguments)
        for aux in auxiliaries:
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
        event_data: Dict[type, Dict[str, Any]],
):
    """
    在解析前执行的操作

    Args:
        decorator: 解析器列表
        event_data: 事件参数字典
    """
    if not decorator.aux_handlers.get('before_parse'):
        return
    for handler in decorator.aux_handlers['before_parse']:
        if handler.aux_type == 'judge':
            await handler.judge_wrapper(event_ctx.get())
        if handler.aux_type == 'supply':
            for k, v in event_data.copy().items():
                event_data[k].update(await handler.supply_wrapper(k, v))


async def after_parse(
        decorator: BaseAuxiliary,
        event_data: Dict[str, Any],
):
    """
    在解析前执行的操作

    Args:
        decorator: 解析器列表
        event_data: 事件参数字典
    """
    if not decorator.aux_handlers.get('after_parse'):
        return
    for handler in decorator.aux_handlers['after_parse']:
        if handler.aux_type == 'supply':
            for k, v in event_data.copy().items():
                event_data[k].update(await handler.supply_wrapper(type(v), {k: v}))


async def execution_complete(decorator: BaseAuxiliary,):
    """
    在解析前执行的操作

    Args:
        decorator: 解析器列表
    """
    if not decorator.aux_handlers.get('execution_complete'):
        return
    for handler in decorator.aux_handlers['execution_complete']:
        if handler.aux_type == 'judge':
            await handler.judge_wrapper(event_ctx.get())


async def param_parser(
        params: List[Tuple[str, Any, Any]],
        event_args: Dict[type, Dict[str, Any]],
        revise: Optional[Dict[str, Any]] = None,
):
    """
    将调用函数提供的参数字典与事件提供的参数字典进行比对，并返回正确的参数字典

    Args:
        params: 调用的函数的参数列表
        event_args: 函数可返回的参数字典
        revise: 修正的参数字典
    Returns:
        函数需要的参数字典
    """
    revise = revise or {}
    arguments_dict = {}
    for name, annotation, default in params:
        if not annotation:
            raise UndefinedRequirement(f"a argument: {{<{annotation}> {name}: {default}}} without annotation")
        if name in revise:
            real_name = revise[name]
            kwarg = event_args.get(annotation, {})
            arguments_dict[name] = kwarg[real_name]
        else:
            kwarg = event_args.get(annotation, {})
            if arg := kwarg.get(name):
                arguments_dict[name] = arg
            elif arg := kwarg.get(annotation.__name__):
                arguments_dict[name] = arg
                revise[name] = annotation.__name__
            elif arg := kwarg.get(str(default)):
                arguments_dict[name] = arg
                revise[name] = str(default)
            elif kwarg:
                k, v = kwarg.popitem()
                arguments_dict[name] = v
                revise[name] = k
            elif default is not Empty:
                arguments_dict[name] = default
        if isinstance(default, BaseAuxiliary):
            aux = default.aux_handlers.get('parsing')
            if not aux:
                continue
            supplys = list(filter(lambda x: x.aux_type == 'supply', aux))
            if default.__class__.__name__ == 'Depend':
                __depend_result = await supplys[0].supply_wrapper(dict, {name: event_args})
                arguments_dict[name] = __depend_result.get(name)
            else:
                __deco_result = await supplys[0].supply_wrapper(annotation, {name: arguments_dict[name]})
                arguments_dict[name] = __deco_result.get(name)
        if name not in arguments_dict:
            raise UnexpectedArgument(f"a argument: {{{annotation} {name}}} without value")
    return arguments_dict, revise
