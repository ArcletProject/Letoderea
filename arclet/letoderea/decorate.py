from typing import TYPE_CHECKING, Callable, Union, Any, overload

from .event import EVENT
from .provider import Provider
from .ref import Deref, generate
from .subscriber import Subscriber, STOP, _compile, Propagator
from .typing import Contexts, TTarget


def bind(*args: Union[Provider, type[Provider]]):
    providers = [p() if isinstance(p, type) else p for p in args]

    def wrapper(target: TTarget) -> TTarget:
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


@overload
def propagate(*funcs: TTarget[Any], prepend: bool = False) -> Callable[[TTarget], TTarget]:
    ...


@overload
def propagate(*funcs: Union[TTarget[Any], Propagator]) -> Callable[[TTarget], TTarget]:
    ...


def propagate(*funcs: Union[TTarget[Any], Propagator], prepend: bool = False):
    def wrapper(target: TTarget, /) -> TTarget:
        if isinstance(target, Subscriber):
            target.propagates(*funcs, prepend=prepend)  # type: ignore
        else:
            if not hasattr(target, "__propagates__"):
                setattr(target, "__propagates__", [(funcs, prepend)])
            else:
                getattr(target, "__propagates__").append((funcs, prepend))
        return target

    return wrapper


if TYPE_CHECKING:

    def bypass_if(predicate: Union[Callable[[Contexts], bool], bool]) -> Callable[[TTarget], TTarget]: ...
    def enter_if(predicate: Union[Callable[[Contexts], bool], bool]) -> Callable[[TTarget], TTarget]: ...
else:
    class _Check(Propagator):
        def __init__(self, predicate: Union[Callable[[Contexts], bool], Deref], result: bool):
            self.predicate = generate(predicate) if isinstance(predicate, Deref) else predicate
            self.result = result

        def check(self, ctx: Contexts):
            if self.predicate(ctx) is not self.result:
                return STOP

        def compose(self):
            yield self.check, True, 0


    def bypass_if(predicate: Union[Callable[[Contexts], bool], Deref]):
        return propagate(_Check(predicate, False))

    def enter_if(predicate: Union[Callable[[Contexts], bool], Deref]):
        return propagate(_Check(predicate, True))


def allow_event(*events: type):
    return bypass_if(lambda ctx: not isinstance(ctx[EVENT], events))


def refuse_event(*events: type):
    return bypass_if(lambda ctx: isinstance(ctx[EVENT], events))
