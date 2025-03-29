from __future__ import annotations

from asyncio import Queue
from typing import Any, Callable, Generic, Awaitable, TypeVar, get_type_hints
from tarina import generic_isinstance

from .provider import Provider, ProviderFactory, get_providers
from .typing import Contexts, is_typed_dict

T = TypeVar("T")
_publishers: dict[str, "Publisher"] = {}


async def _supplier(event: Any, context: Contexts):
    if isinstance(event, dict):
        return context.update(event)
    return context.update({k: v for k, v in vars(event).items() if not k.startswith("_")})


class Publisher(Generic[T]):
    id: str

    def __init__(self, target: type[T], id_: str | None = None, supplier: Callable[[T, Contexts], Awaitable[Contexts | None]] | None = None, queue_size: int = -1):
        self.providers: list[Provider | ProviderFactory] = get_providers(target)
        if not isinstance(target, type) and not id_:  # pragma: no cover
            raise TypeError("Publisher with generic type must have a name")
        self.id = id_ or getattr(target, "__publisher__", f"$event:{target.__module__}.{target.__name__}")
        self.target = target
        self.supplier: Callable[[T, Contexts], Awaitable[Contexts | None]] = supplier or _supplier
        if hasattr(target, "gather"):
            self.supplier = target.gather  # type: ignore
        self.event_queue = Queue(queue_size)
        self.validate = (
            (lambda x: generic_isinstance(x, target))
            if is_typed_dict(target) or not isinstance(target, type)
            else (lambda x: isinstance(x, target))
        )
        _publishers[self.id] = self

    def gather(self, func: Callable[[T, Contexts], Awaitable[Contexts | None]]):
        self.supplier = func
        return func

    def __repr__(self):
        return f"{self.__class__.__name__}::{self.id}"

    def unsafe_push(self, event: T) -> None:
        """将事件放入队列，等待被 event system 主动轮询; 该方法可能引发 QueueFull 异常"""
        self.event_queue.put_nowait(event)

    async def push(self, event: T):
        """将事件放入队列，等待被 event system 主动轮询"""
        await self.event_queue.put(event)

    async def supply(self) -> T:
        """被动提供事件方法， 由 event system 主动轮询"""
        return await self.event_queue.get()

    def dispose(self):
        _publishers.pop(self.id, None)

    def bind(self, *args: Provider | type[Provider] | ProviderFactory | type[ProviderFactory]) -> None:
        """增加间接 Provider"""
        self.providers.extend(p() if isinstance(p, type) else p for p in args)

    def unbind(
        self,
        arg: Provider | type[Provider] | ProviderFactory | type[ProviderFactory],
    ) -> None:
        """移除间接 Provider"""
        idx = [i for i, p in enumerate(self.providers) if (isinstance(arg, (ProviderFactory, Provider)) and p == arg) or (isinstance(arg, type) and isinstance(p, arg))]
        for i in reversed(idx):
            self.providers.pop(i)


def filter_publisher(target: type[T]) -> Publisher[T] | None:
    if (label := getattr(target, "__publisher__", f"$event:{target.__module__}.{target.__name__}")) in _publishers:
        return _publishers[label]
    return next((pub for pub in _publishers.values() if pub.target == target), None)


def search_publisher(event: T) -> Publisher[T] | None:
    if pub := _publishers.get(getattr(event, "__publisher__", f"$event:{type(event).__module__}{type(event).__name__}")):
        return pub
    return next((pub for pub in _publishers.values() if pub.validate(event)), None)


def define(
    target: type[T],
    supplier: Callable[[T, Contexts], Awaitable[Contexts | None]] | None = None,
    name: str | None = None,
) -> Publisher[T]:
    if name and name in _publishers:
        return _publishers[name]
    if (_id := getattr(target, "__publisher__", f"$event:{target.__module__}.{target.__name__}")) in _publishers:
        return _publishers[_id]
    return Publisher(target, name, supplier)


def gather(func: Callable[[T, Contexts], Awaitable[Contexts | None]]):
    target: type[T] = next(iter(get_type_hints(func).values()))  # type: ignore
    pub = filter_publisher(target) or define(target)
    pub.supplier = func
    return func
