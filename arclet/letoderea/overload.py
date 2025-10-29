from __future__ import annotations

import itertools
from inspect import Signature
from asyncio import Queue
from typing import TypeVar, Any, get_args
from collections import defaultdict
from collections.abc import Callable, Awaitable
from typing_extensions import ParamSpec

from tarina import signatures, generic_isinstance, Empty
from tarina.generic import origin_is_union, get_origin

from .core import post
from .provider import TProviders, provide
from .typing import Contexts, TCallable
from .scope import Scope
from .publisher import Publisher, _publishers

T = TypeVar("T")
P = ParamSpec("P")


_collectors: defaultdict[str, dict[tuple, CollectedPublisher]] = defaultdict(dict)


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
        for key, val in event.items():
            context[f"${self.id}_{key}"] = val
        return context

    def validate(self, x):
        if not isinstance(x, dict):
            return False
        if not self._required_keys.issuperset(x.keys()):
            return False
        for key, val in x.items():
            if key in self._params and self._params[key][0] and not generic_isinstance(val, self._params[key][0]):
                return False
        return True

    def dispose(self):  # pragma: no cover
        _publishers.pop(self.id, None)
        key = self.id.split("::")[0]
        annos = [[(name, ann) for ann in get_args(anno)] if origin_is_union(get_origin(anno)) else [(name, anno)] for name, anno, _ in self._params]
        for args in itertools.product(*annos):
            if args in _collectors[key] and _collectors[key][args] is self:
                del _collectors[key][args]


class Overloader:
    def __init__(self, name: str, *, priority: int = 16, providers: TProviders | None = None, once: bool = False):
        self.name = name
        self._functions: dict[tuple, Callable[..., Any]] = {}
        self.priority = priority
        self.providers = providers
        self.once = once
        self.scope = Scope.of(name)

    def overload(self, func: TCallable) -> TCallable:
        params = signatures(func)
        annos = [[(name, ann) for ann in get_args(anno)] if origin_is_union(get_origin(anno)) else [(name, anno)] for name, anno, _ in params]
        matrix = list(itertools.product(*annos))
        if any(args in _collectors[self.name] for args in matrix):  # pragma: no cover
            pub = _collectors[self.name][matrix[0]]
        else:
            pub = CollectedPublisher(f"{self.name}::{func.__qualname__}_{hash(matrix[0])}", params)
            for args in matrix:
                _collectors[self.name][args] = pub
            pub.providers = [provide(ann, target=name, call=f"${pub.id}_{name}") for slot in annos for name, ann in slot]
        self.scope.register(
            func,
            priority=self.priority,
            providers=self.providers,
            once=self.once,
            skip_req_missing=True,
            publisher=pub,
        )
        return func

    def dispose(self):  # pragma: no cover
        self.scope.dispose()
        key = self.name
        for args in list(_collectors[key].keys()):
            _collectors[key][args].dispose()

    def define(self, func: Callable[P, T]) -> Callable[P, Awaitable[T]]:
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            sig = Signature.from_callable(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            event = {k: v for k, v in bound.arguments.items() if v is not None}
            result = await post(event, self.scope)
            return result.value  # type: ignore
        return wrapper
