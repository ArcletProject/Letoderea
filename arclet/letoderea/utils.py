import inspect
from functools import lru_cache
from typing import Type, Union, Callable, Any

from .entities.condition import TemplateCondition
from .entities.event import TemplateEvent

Event_T = Union[Type[TemplateEvent], TemplateEvent]
Condition_T = Union[Type[TemplateCondition], TemplateCondition]


class ArgumentPackage:
    name: str
    annotation: Any
    value: Any

    __slots__ = ("name", "value", "annotation")

    def __init__(self, name, annotation, value):
        self.name = name
        self.annotation = annotation
        self.value = value

    def __repr__(self):
        return (
            "<ArgumentPackage name={0} annotation={1} value={2}".format(
                self.name, self.annotation, self.value
            )
        )


async def run_always_await(callable_target, *args, **kwargs):
    if iscoroutinefunction(callable_target):
        return await callable_target(*args, **kwargs)
    return callable_target(*args, **kwargs)


@lru_cache(4096)
def argument_analysis(callable_target: Callable):
    return [
        (
            name,
            param.annotation if param.annotation is not inspect.Signature.empty else None,
            param.default if param.default is not inspect.Signature.empty else None,
        )
        for name, param in inspect.signature(callable_target).parameters.items()
    ]


@lru_cache(4096)
def iscoroutinefunction(o):
    return inspect.iscoroutinefunction(o)


def event_class_generator(target=TemplateEvent):
    for i in target.__subclasses__():
        yield i
        if i.__subclasses__():
            yield from event_class_generator(i)


def search_event(name: str):
    for i in event_class_generator():
        if i.__name__ == name:
            return i
