from asyncio import Queue
from typing import Callable, TypeVar, overload, Generic
from typing_extensions import ParamSpec

from tarina import signatures, generic_isinstance

from .typing import Contexts
from .publisher import Publisher, _publishers

T = TypeVar("T")
P = ParamSpec("P")


class _Dispatch(Generic[P, T]):
    def __init__(self, fn: Callable[P, T]):
        self.fn = fn

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        return self.fn(*args, **kwargs)


D = TypeVar("D", bound=_Dispatch)


class DispatchPublisher(Publisher[D]):
    id: str

    def __init__(self, target: D, id_: str, queue_size: int = -1):
        # self.providers: list[Provider | ProviderFactory] = get_providers(target)
        # if not isinstance(target, type) and not id_:  # pragma: no cover
        #     raise TypeError("Publisher with generic type must have a name")
        # self.id = id_ or getattr(target, "__publisher__", f"$event:{target.__module__}.{target.__name__}")
        # self.target = target
        # self.supplier: Callable[[T, Contexts], Awaitable[Contexts | None]] = supplier or _supplier
        # if hasattr(target, "gather"):
        #     self.supplier = target.gather  # type: ignore
        self.event_queue = Queue(queue_size)
        # self.validate = (
        #     (lambda x: generic_isinstance(x, target))
        #     if is_typed_dict(target) or not isinstance(target, type)
        #     else (lambda x: isinstance(x, target))
        # )
        self.target = target
        self.id = id_
        _publishers[self.id] = self

    def _supplier(self, event, context: Contexts):
        for i, (name, anno, default) in enumerate(signatures(self.target)):
            context[name] = event[i]

    def validate(self, x):
        for i, (name, anno, default) in enumerate(signatures(self.target)):
            if not generic_isinstance(x[i], anno):
                return False
        return True


@overload
def collect_event(*, name: str) -> Callable[[Callable[P, T]], _Dispatch[P, T]]: ...


@overload
def collect_event(func: Callable[P, T]) -> _Dispatch[P, T]: ...


def collect_event(func: Callable[P, T] | None = None, *, name: str | None = None):
    def wrapper(fn: Callable[P, T], /):
        _name = name or fn.__name__
        disp = _Dispatch(fn)
        _p = DispatchPublisher(disp, id_=_name)
        return disp

    if func:
        return wrapper(func)
    return wrapper
