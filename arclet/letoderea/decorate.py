from typing import Callable, Type, TypeVar, Union, Optional, TYPE_CHECKING

from . import Scope
from .auxiliary import BaseAuxiliary, AuxType, auxilia
from .context import system_ctx
from .event import BaseEvent
from .provider import Provider
from .subscriber import Subscriber, _compile
from .typing import Contexts
from .exceptions import ParsingStop
from .ref import generate, Deref

TWrap = TypeVar("TWrap", bound=Union[Callable, Subscriber])


def bind(*args: Union[BaseAuxiliary, Provider, Type[Provider]]):
    auxiliaries = list(filter(lambda x: isinstance(x, BaseAuxiliary), args))
    providers = list(filter(lambda x: not isinstance(x, BaseAuxiliary), args))
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
            if not hasattr(target, "__auxiliaries__"):
                setattr(target, "__auxiliaries__", auxiliaries)
            else:
                getattr(target, "__auxiliaries__").extend(auxiliaries)
        return target

    return wrapper


def subscribe(*event: Type[BaseEvent]):
    es = system_ctx.get()

    def wrapper(target: TWrap) -> TWrap:
        if not es:
            return target
        if isinstance(target, Subscriber):
            for e in event:
                es._backend_publisher.add_subscriber(e, target)  # noqa
            return target
        return es.on(*event)(target)

    return wrapper


if TYPE_CHECKING:
    def bypass_if(predicate: Union[Callable[[Contexts], bool], bool]):
        ...
else:
    def bypass_if(predicate: Union[Callable[[Contexts], bool], Deref]):
        _predicate = generate(predicate) if isinstance(predicate, Deref) else predicate

        def _prepare(context: Contexts) -> Optional[bool]:
            if _predicate(context):
                raise ParsingStop()
            return True

        inner = auxilia(AuxType.judge, prepare=_prepare)

        def wrapper(target: TWrap) -> TWrap:
            if isinstance(target, Subscriber):
                target.auxiliaries[Scope.prepare].append(inner)
            else:
                if not hasattr(target, "__auxiliaries__"):
                    setattr(target, "__auxiliaries__", [inner])
                else:
                    getattr(target, "__auxiliaries__").append(inner)
            return target

        return wrapper
