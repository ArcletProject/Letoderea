from typing import TYPE_CHECKING, Any, Callable, Union, overload
from typing_extensions import Self
from functools import wraps

from .provider import Provider
from .ref import Deref, generate
from .subscriber import STOP, Propagator, Subscriber, _compile
from .typing import EVENT, Contexts, TCallable


def bind(*args: Union[Provider, type[Provider]]):
    providers = [p() if isinstance(p, type) else p for p in args]

    def wrapper(target: TCallable) -> TCallable:
        if isinstance(target, Subscriber):
            target.providers.extend(providers)
            target.params = _compile(target.callable_target, target.providers)
        else:
            if not hasattr(target, "__providers__"):
                setattr(target, "__providers__", providers)
            else:
                getattr(target, "__providers__").extend(providers)
        return target  # type: ignore

    return wrapper


@overload
def propagate(*funcs: Callable[..., Any], prepend: bool = False) -> Callable[[TCallable], TCallable]: ...


@overload
def propagate(*funcs: Union[Callable[..., Any], Propagator]) -> Callable[[TCallable], TCallable]: ...


def propagate(*funcs: Union[Callable[..., Any], Propagator], prepend: bool = False):
    def wrapper(target: TCallable, /) -> TCallable:
        if isinstance(target, Subscriber):
            target.propagates(*funcs, prepend=prepend)
        else:
            if not hasattr(target, "__propagates__"):
                setattr(target, "__propagates__", [(funcs, prepend)])
            else:
                getattr(target, "__propagates__").append((funcs, prepend))
        return target  # type: ignore

    return wrapper


class _Check(Propagator):
    def __init__(self, result: bool):
        self.predicates = []
        self.result = result

    if TYPE_CHECKING:
        def append(self, predicate: Union[Callable[..., bool], bool]) -> Self: ...
    else:
        def append(self, predicate: Union[Callable[..., bool], Deref]) -> Self:
            self.predicates.append(generate(predicate) if isinstance(predicate, Deref) else predicate)
            return self

    __and__ = append
    __or__ = append

    def checkers(self):
        for predicate in self.predicates:

            @wraps(predicate)
            async def _(*args, _func=predicate, **kwargs):
                if _func(*args, **kwargs) is not self.result:
                    return STOP

            yield _

    def compose(self):
        for checker in self.checkers():
            yield checker, True, 0

    def __call__(self, func: TCallable) -> TCallable:
        return propagate(self)(func)


class _CheckBuilder:
    def __init__(self, result: bool):
        self.result = result

    if TYPE_CHECKING:
        def __call__(self, predicate: Union[Callable[..., bool], bool]) -> _Check: ...
    else:
        def __call__(self, predicate: Union[Callable[..., bool], Deref]) -> _Check:
            return _Check(self.result).append(generate(predicate) if isinstance(predicate, Deref) else predicate)

    __and__ = __call__
    __or__ = __call__


bypass_if = _CheckBuilder(False)
enter_if = _CheckBuilder(True)


def allow_event(*events: type):  # pragma: no cover
    def _(ctx: Contexts) -> bool:
        return isinstance(ctx[EVENT], events)

    return enter_if(_)


def refuse_event(*events: type):  # pragma: no cover
    def _(ctx: Contexts) -> bool:
        return isinstance(ctx[EVENT], events)

    return bypass_if(_)
