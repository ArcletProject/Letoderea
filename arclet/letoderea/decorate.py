from typing import TYPE_CHECKING, Callable, Optional, Union

from .auxiliary import BaseAuxiliary, Interface, auxilia
from .context import scope_ctx
from .core import es
from .event import BaseEvent, EVENT
from .provider import Provider
from .ref import Deref, generate
from .subscriber import Subscriber, _compile
from .typing import Contexts, TTarget


def bind(*args: Union[BaseAuxiliary, Provider, type[Provider]]):
    auxiliaries = [a for a in args if isinstance(a, BaseAuxiliary)]
    providers = [p for p in args if not isinstance(p, BaseAuxiliary)]
    providers = [p() if isinstance(p, type) else p for p in providers]

    def wrapper(target: TTarget) -> TTarget:
        if isinstance(target, Subscriber):
            target.providers.extend(providers)
            target.params = _compile(target.callable_target, target.providers)
        else:
            if not hasattr(target, "__providers__"):
                setattr(target, "__providers__", providers)
            else:
                getattr(target, "__providers__").extend(providers)
            if not hasattr(target, "__auxiliaries__"):
                setattr(target, "__auxiliaries__", auxiliaries)
            else:
                getattr(target, "__auxiliaries__").extend(auxiliaries)
        return target

    return wrapper


def subscribe(*event: type[BaseEvent]):

    def wrapper(target: TTarget) -> TTarget:
        if scope := scope_ctx.get():
            return scope.register(events=event)(target)
        return es.on(event)(target)

    return wrapper


if TYPE_CHECKING:

    def bypass_if(predicate: Union[Callable[[Contexts], bool], bool]) -> Callable[[TTarget], TTarget]: ...

else:

    def bypass_if(predicate: Union[Callable[[Contexts], bool], Deref]):
        _predicate = generate(predicate) if isinstance(predicate, Deref) else predicate

        def _prepare(interface: Interface) -> Optional[bool]:
            return not _predicate(interface.ctx)

        inner = auxilia("bypass_if", _prepare)

        def wrapper(target: TTarget) -> TTarget:
            if isinstance(target, Subscriber):
                target.auxiliaries["prepare"].append(inner)
            else:
                if not hasattr(target, "__auxiliaries__"):
                    setattr(target, "__auxiliaries__", [inner])
                else:
                    getattr(target, "__auxiliaries__").append(inner)
            return target

        return wrapper


def allow_event(*events: type[BaseEvent]):
    return bypass_if(lambda ctx: not isinstance(ctx[EVENT], events))


def refuse_event(*events: type[BaseEvent]):
    return bypass_if(lambda ctx: isinstance(ctx[EVENT], events))
