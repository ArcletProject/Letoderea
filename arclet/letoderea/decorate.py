from typing import Callable, TypeVar, Union, Type

from .subscriber import Subscriber
from .provider import Provider
from .auxiliary import BaseAuxiliary


TWrap = TypeVar("TWrap", bound=Union[Callable, Subscriber])


def wrap_aux(*aux: BaseAuxiliary):
    def wrapper(target: TWrap) -> TWrap:
        _target = target if isinstance(target, Callable) else target.callable_target
        if not hasattr(_target, "__auxiliaries__"):
            setattr(_target, "__auxiliaries__", list(aux))
        else:
            getattr(_target, "__auxiliaries__").extend(aux)
        return target

    return wrapper


def bind(*providers: Union[Provider, Type[Provider]]):
    providers = [p() if isinstance(p, type) else p for p in providers]

    def wrapper(target: TWrap) -> TWrap:
        _target = target if isinstance(target, Callable) else target.callable_target
        if not hasattr(_target, "__providers__"):
            setattr(_target, "__providers__", providers)
        else:
            getattr(_target, "__providers__").extend(providers)
        return target

    return wrapper
