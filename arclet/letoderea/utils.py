import inspect
from contextlib import contextmanager
from contextvars import ContextVar, Token
from functools import lru_cache
from typing import Type, Union, Callable, Any, Iterable, List, Generic, TypeVar

from .entities.event import TemplateEvent

Empty = inspect.Signature.empty
TEvent = Union[Type[TemplateEvent], TemplateEvent]
T = TypeVar("T")
D = TypeVar("D")


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
            param.default  # if param.default is not inspect.Signature.empty else None,
        )
        for name, param in inspect.signature(callable_target).parameters.items()
    ]


@lru_cache(4096)
def iscoroutinefunction(o):
    return inspect.iscoroutinefunction(o)


def group_dict(iterable: Iterable, key_callable: Callable[[Any], Any]):
    temp = {}
    for i in iterable:
        k = key_callable(i)
        temp[k] = i
    return temp


def event_class_generator(target=TemplateEvent):
    for i in target.__subclasses__():
        yield i
        if i.__subclasses__():
            yield from event_class_generator(i)


def search_event(name: str):
    for i in event_class_generator():
        if i.__name__ == name:
            return i


@lru_cache(None)
def gather_inserts(event: Union[Type[TemplateEvent], TemplateEvent]) -> "List[TEvent]":
    inserts = getattr(event, "inserts", [])
    result: "List[TEvent]" = [event]

    for i in inserts:
        if issubclass(i, TemplateEvent):
            result.extend(gather_inserts(i))
        else:
            result.append(i)
    return result


class ContextModel(Generic[T]):
    current_ctx: ContextVar[T]

    def __init__(self, name: str) -> None:
        self.current_ctx = ContextVar(name)

    def get(self, default: Union[T, D] = None) -> Union[T, D]:
        return self.current_ctx.get(default)

    def set(self, value: T):
        return self.current_ctx.set(value)

    def reset(self, token: Token):
        return self.current_ctx.reset(token)

    @contextmanager
    def use(self, value: T):
        token = self.set(value)
        yield
        self.reset(token)
