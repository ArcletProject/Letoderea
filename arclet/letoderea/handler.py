import traceback
from inspect import isclass
from typing import Tuple, Dict, Any, Union, Callable, List, get_args
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
    is_subscriber = isinstance(target, Subscriber)
    auxiliaries = target.auxiliaries if is_subscriber else []
    callable_target = target.callable_target if is_subscriber else target
    event_data = target.internal_arguments.copy() if is_subscriber else {}
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
        arguments = await param_parser(target_param, event_data, revise)
        if is_subscriber:
            target.revise_dispatches = revise
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
    ???????????????????????????

    Args:
        decorator: ???????????????
        event_data: ??????????????????
    """
    if not decorator.aux_handlers.get('before_parse'):
        return
    for handler in decorator.aux_handlers['before_parse']:
        if handler.aux_type == 'judge':
            await handler.judge_wrapper(decorator, event_ctx.get())
        if handler.aux_type == 'supply':
            for k, v in event_data.copy().items():
                if handler.keep:
                    event_data.update(await handler.supply_wrapper_keep(decorator, k, v))
                else:
                    event_data[k].update(await handler.supply_wrapper(decorator, k, v))


async def after_parse(
        decorator: BaseAuxiliary,
        event_data: Dict[str, Any],
):
    """
    ???????????????????????????

    Args:
        decorator: ???????????????
        event_data: ??????????????????
    """
    if not decorator.aux_handlers.get('after_parse'):
        return
    for handler in decorator.aux_handlers['after_parse']:
        if handler.aux_type == 'supply':
            for k, v in event_data.copy().items():
                if handler.keep:
                    r = await handler.supply_wrapper_keep(decorator, type(v), {k: v})
                    event_data.update(r.popitem()[1])
                else:
                    event_data[k].update(await handler.supply_wrapper(decorator, type(v), {k: v}))


async def execution_complete(decorator: BaseAuxiliary,):
    """
    ???????????????????????????

    Args:
        decorator: ???????????????
    """
    if not decorator.aux_handlers.get('execution_complete'):
        return
    for handler in decorator.aux_handlers['execution_complete']:
        if handler.aux_type == 'judge':
            await handler.judge_wrapper(decorator, event_ctx.get())


async def param_parser(
        params: List[Tuple[str, Any, Any]],
        event_args: Dict[type, Dict[str, Any]],
        revise: Dict[str, Any],
):
    """
    ???????????????????????????????????????????????????????????????????????????????????????????????????????????????

    Args:
        params: ??????????????????????????????
        event_args: ??????????????????????????????
        revise: ?????????????????????
    Returns:
        ???????????????????????????
    """
    arguments_dict = {}
    for name, annotation, default in params:
        if not annotation or annotation == Any:
            for _m_args in event_args.values():
                if arg := _m_args.get(name):
                    arguments_dict[name] = arg
                    break
                elif arg := _m_args.get(str(default)):
                    arguments_dict[name] = arg
                    revise[name] = str(default)
                    break
                elif default is not Empty:
                    arguments_dict[name] = default
                    break
                else:
                    raise UndefinedRequirement(f"{name}'s annotation is undefined")
        else:
            if not (kwarg := event_args.get(annotation, {})):
                if isinstance(annotation, str):
                    for t in event_args:
                        if t.__name__ == annotation:
                            kwarg = event_args[t]
                            break
                elif isclass(annotation):
                    for t in event_args:
                        if issubclass(t, annotation):
                            kwarg = event_args[t]
                            break
                elif annotation.__class__.__name__ in "_GenericAlias":
                    for anno in get_args(annotation):
                        if kwarg := event_args.get(anno, {}):
                            annotation = anno
                            break
                        for t in event_args:
                            if isclass(anno) and issubclass(t, anno):
                                kwarg = event_args[t]
                                break

            if isinstance(annotation, str):
                annotation_name = annotation
            else:
                annotation_name = annotation.__name__
            if name in revise:
                real_name = revise[name]
                arguments_dict[name] = kwarg[real_name]
            elif arg := kwarg.get(name):
                arguments_dict[name] = arg
            elif arg := kwarg.get(annotation_name):
                arguments_dict[name] = arg
                revise[name] = annotation_name
            elif arg := kwarg.get(str(default)):
                arguments_dict[name] = arg
                revise[name] = str(default)
            elif kwarg:
                k, v = kwarg.popitem()
                arguments_dict[name] = v
                revise[name] = k
            elif default is not Empty:  # and isclass(annotation) and isinstance(default, annotation):
                arguments_dict[name] = default

        if isinstance(default, BaseAuxiliary):
            aux = default.aux_handlers.get('parsing')
            if not aux:
                continue
            supplys = list(filter(lambda x: x.aux_type == 'supply', aux))
            if default.__class__.__name__ == 'Depend':
                _depend_result = await supplys[0].supply_wrapper(default, dict, {name: event_args})
                if (res := _depend_result.get(name)) != event_args:
                    arguments_dict[name] = res
            else:
                _deco_result = await supplys[0].supply_wrapper(default, annotation, {name: arguments_dict[name]})
                if (res := _deco_result.get(name)) != arguments_dict[name]:
                    arguments_dict[name] = res
        if name not in arguments_dict:
            raise UnexpectedArgument(f"a argument: {{{annotation} {name}}} without value")
    return arguments_dict
