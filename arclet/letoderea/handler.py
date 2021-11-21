import traceback
from typing import Tuple, Dict, Type, Any, Union, Callable
from .entities.subscriber import Subscriber
from .entities.event import Insertable, ParamRet
from .exceptions import UndefinedRequirement, UnexpectedArgument, MultipleInserter, RepeatedInserter
from .utils import argument_analysis, run_always_await
from .entities.decorator import TemplateDecorator


async def await_exec_target(
        target: Union[Subscriber, Callable],
        event_data_handler: Union[Callable[[], ParamRet], ParamRet]
):
    is_subscriber = False
    if isinstance(target, Subscriber):
        is_subscriber = True
    decorators = target.decorators if is_subscriber else []
    callable_target = target.callable_target if is_subscriber else target
    target_param = argument_analysis(callable_target)
    try:
        event_args = before_parser(decorators, event_data_handler)
        arguments = param_parser(target_param, event_args)
        real_arguments = after_parser(decorators, arguments)
        result = await run_always_await(callable_target, **real_arguments)
    except (UnexpectedArgument, UndefinedRequirement):
        traceback.print_exc()
        raise
    except Exception as e:
        traceback.print_exc()
        raise e
    return result


def decorator_before_handler(decorator: TemplateDecorator, event_args):
    if "before_parser" not in decorator.__disable__:
        for k, v in event_args.items():
            if not decorator.may_target_type or (decorator.may_target_type and type(v) is decorator.may_target_type):
                result = decorator.supply_wrapper(k, v)
                if result is None:
                    continue
                event_args.update(result)
    return event_args


def inserter_handler(inserters: Tuple[Union[Type[Insertable], Insertable]]) -> Dict[str, Any]:
    extra: Dict[str, Any] = {}
    used_inserter = []
    for inserter in inserters:
        if inserter in used_inserter:
            raise RepeatedInserter("a inserter cannot insert twice")
        (event_inserter, event_args) = inserter.get_params()
        if event_inserter:
            raise MultipleInserter("a inserter cannot used another inserter")
        extra.update(event_args)
        used_inserter.append(inserter)
    return extra


def before_parser(decorators, event_data_handler):
    (event_inserter, event_args) = event_data_handler()
    try:
        if event_inserter:
            event_args.update(inserter_handler(event_inserter))
    except (RepeatedInserter, MultipleInserter):
        traceback.print_exc()
    finally:
        if decorators:
            for decorator in decorators:
                event_args = decorator_before_handler(decorator, event_args)
        return event_args


def param_parser(params, event_args):
    """
    将调用函数提供的参数字典与事件提供的参数字典进行比对，并返回正确的参数字典

    Args:
        params: 调用的函数的参数字典
        event_args: 函数可返回的参数字典
    Returns:
        函数需要的参数字典
    """
    arguments_dict = {}
    for name, annotation, default in params:
        if not annotation:
            raise UndefinedRequirement(f"a argument: {{<{annotation}> {name}: {default}}} without annotation")
        elif isinstance(default, str) and default in event_args:
            arguments_dict.setdefault(name, event_args[default])
        elif annotation.__name__ in event_args:
            arguments_dict.setdefault(name, event_args.get(annotation.__name__))
        elif name in event_args:
            arguments_dict.setdefault(name, event_args[name])
        elif default is not None:
            arguments_dict[name] = default
            if isinstance(default, Callable):
                arguments_dict[name] = default()
        if name not in arguments_dict:
            raise UnexpectedArgument(f"a unexpected extra argument: {{{annotation} {name}: {default}}}")

    return arguments_dict


def decorator_after_handler(decorator: TemplateDecorator, argument):
    if "after_parser" not in decorator.__disable__:
        for k, v in argument.items():
            result = decorator.supply_wrapper(k, v)
            if result is None:
                continue
            argument.update(result)
    return argument


def after_parser(decorators, argument):
    if decorators:
        for decorator in decorators:
            argument = decorator_after_handler(decorator, argument)
    return argument
