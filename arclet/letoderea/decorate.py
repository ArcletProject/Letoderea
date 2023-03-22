from typing import Callable, TypeVar, Union, Type

from .subscriber import Subscriber, _compile
from .provider import Provider
from .event import BaseEvent
from .auxiliary import BaseAuxiliary
from .context import system_ctx


TWrap = TypeVar("TWrap", bound=Union[Callable, Subscriber])


def wrap_aux(*aux: BaseAuxiliary):
    def wrapper(target: TWrap) -> TWrap:
        if not isinstance(target, Subscriber):
            if not hasattr(target, "__auxiliaries__"):
                setattr(target, "__auxiliaries__", list(aux))
            else:
                getattr(target, "__auxiliaries__").extend(aux)
        return target

    return wrapper


def bind(*providers: Union[Provider, Type[Provider]]):
    providers = [p() if isinstance(p, type) else p for p in providers]

    def wrapper(target: TWrap) -> TWrap:
        if isinstance(target, Subscriber):
            target.providers.extend(providers)
            target.params = _compile(target.callable_target, target.providers)
        else:
            if not hasattr(target, "__providers__"):
                setattr(target, "__providers__", providers)
            else:
                getattr(target, "__providers__").extend(providers)
        return target

    return wrapper


def register(*event: Type[BaseEvent]):
    es = system_ctx.get()

    def wrapper(target: TWrap) -> TWrap:
        if not es:
            return target
        if isinstance(target, Subscriber):
            for e in event:
                es._backend_publisher.add_subscriber(e, target)  # noqa
            return target
        return es.register(*event)(target)

    return wrapper
