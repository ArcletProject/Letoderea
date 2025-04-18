from __future__ import annotations

import itertools
from asyncio import Queue
from typing import Callable, TypeVar, Any, overload, get_args
from typing_extensions import ParamSpec

from tarina import signatures, generic_isinstance, Empty
from tarina.generic import origin_is_union, get_origin

from .subscriber import Subscriber
from .provider import TProviders, provide
from .typing import Contexts
from .scope import scope_ctx, _scopes
from .publisher import Publisher, _publishers

T = TypeVar("T")
P = ParamSpec("P")


_collectors: dict[tuple, CollectedPublisher] = {}


class CollectedPublisher(Publisher[T]):

    def __init__(self, id_: str, params: list[tuple[str, Any, Any]], queue_size: int = -1):
        self.event_queue = Queue(queue_size)
        self.target = object
        self.supplier = self._supplier
        self.id = id_
        _publishers[self.id] = self
        self._params = {name: (anno, de) for name, anno, de in params}
        self._required_keys = {name for name, _, de in params if de is Empty and name != "event"}
        self.providers = []

    async def _supplier(self, event, context: Contexts):
        if isinstance(event, (tuple, list)):
            data = {name: event[i] for i, name in enumerate(self._params) if i < len(event)}
        elif isinstance(event, dict):
            data = event
        else:
            try:  # pragma: no cover
                data = {key: val for key, val in vars(event).items()}
            except TypeError:  # pragma: no cover
                data = {}
        for key, val in data.items():
            context[f"${self.id}_{key}_{type(val)}"] = val

    def validate(self, x):
        if isinstance(x, (tuple, list)):
            data = {name: x[i] for i, name in enumerate(self._params) if i < len(x)}
        elif isinstance(x, dict):
            data = x
        else:
            try:
                data = {key: val for key, val in vars(x).items()}
            except TypeError:
                data = {}
        if not self._required_keys.issubset(data.keys()):
            return False
        for key, val in data.items():
            if key in self._params and self._params[key][0] and not generic_isinstance(val, self._params[key][0]):
                return False
        return True

    def dispose(self):  # pragma: no cover
        _publishers.pop(self.id, None)
        annos = [[(name, ann) for ann in get_args(anno)] if origin_is_union(get_origin(anno)) else [(name, anno)] for name, anno, _ in self._params]
        for args in itertools.product(*annos):
            if args in _collectors and _collectors[args] is self:
                del _collectors[args]


@overload
def collect(func: Callable[..., T], *, priority: int = 16, providers: TProviders | None = None, once: bool = False) -> Subscriber[T]:
    ...


@overload
def collect(*, priority: int = 16, providers: TProviders | None = None, once: bool = False) -> Callable[[Callable[..., T]], Subscriber[T]]:
    ...


def collect(func: Callable[..., Any] | None = None, priority: int = 16, providers: TProviders | None = None, once: bool = False):
    if not (scope := scope_ctx.get()):
        scope = _scopes["$global"]

    def wrapper(target: Callable[..., T], /) -> Subscriber[T]:
        params = signatures(target)
        annos = [[(name, ann) for ann in get_args(anno)] if origin_is_union(get_origin(anno)) else [(name, anno)] for name, anno, _ in params]
        matrix = list(itertools.product(*annos))
        if any(args in _collectors for args in matrix):
            pub = _collectors[matrix[0]]
        else:
            pub = CollectedPublisher(f"collect_{target.__qualname__}", params)
            for args in matrix:
                _collectors[args] = pub
            pub.providers = [provide(ann, target=name, call=f"${pub.id}_{name}_{ann}") for slot in annos for name, ann in slot]
        return scope.register(target, priority=priority, providers=providers, once=once, skip_req_missing=True, publisher=pub)

    if func:
        return wrapper(func)
    return wrapper
