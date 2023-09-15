from typing import Callable, Type, Union, Optional, TYPE_CHECKING

from .auxiliary import BaseAuxiliary, AuxType, auxilia, Scope
from .context import system_ctx
from .event import BaseEvent
from .provider import Provider
from .typing import Contexts, TCallable, TTarget
from .exceptions import ParsingStop
from .subscriber import Subscriber, _compile
from .ref import generate, Deref


def bind(*args: Union[BaseAuxiliary, Provider, Type[Provider]]):
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


def subscribe(*event: Type[BaseEvent]):
    es = system_ctx.get()

    def wrapper(target: TCallable) -> TCallable:
        return es.on(*event)(target) if es else target

    return wrapper


if TYPE_CHECKING:
    def bypass_if(predicate: Union[Callable[[Contexts], bool], bool]) -> Callable[[TTarget], TTarget]:
        ...
else:
    def bypass_if(predicate: Union[Callable[[Contexts], bool], Deref]):
        _predicate = generate(predicate) if isinstance(predicate, Deref) else predicate

        def _prepare(context: Contexts) -> Optional[bool]:
            if _predicate(context):
                raise ParsingStop()
            return True

        inner = auxilia(AuxType.judge, prepare=_prepare)

        def wrapper(target: TTarget) -> TTarget:
            if isinstance(target, Subscriber):
                target.auxiliaries[Scope.prepare].append(inner)
            else:
                if not hasattr(target, "__auxiliaries__"):
                    setattr(target, "__auxiliaries__", [inner])
                else:
                    getattr(target, "__auxiliaries__").append(inner)
            return target

        return wrapper

def is_event(*events: Type[BaseEvent]):
    return bypass_if(lambda ctx: not isinstance(ctx["$event"], events))

def not_event(*events: Type[BaseEvent]):
    return bypass_if(lambda ctx: isinstance(ctx["$event"], events))
