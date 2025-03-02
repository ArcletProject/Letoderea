from __future__ import annotations

from asyncio import Queue
from collections.abc import Mapping
from typing import Any, Callable, Generic, Awaitable, Protocol, TypeVar, runtime_checkable

from tarina import generic_isinstance

from .typing import is_typed_dict

T = TypeVar("T")


@runtime_checkable
class Publishable(Protocol):
    __publisher__: str


_publishers: dict[str, "Publisher"] = {}


async def _supplier(event: Any) -> dict[str, Any]:
    if isinstance(event, dict):
        return event
    ctx = vars(event)
    return {k: v for k, v in ctx.items() if not k.startswith("_")}


async def _gather(event: Any):
    ctx = {}
    await event.gather(ctx)
    return ctx


class Publisher(Generic[T]):
    id: str

    def __init__(self, target: type[T], id_: str | None = None, supplier: Callable[[T], Awaitable[Mapping[str, Any]]] | None = None, queue_size: int = -1):
        if id_:
            self.id = id_
        elif hasattr(target, "__publisher__"):
            self.id = target.__publisher__  # type: ignore
        else:
            self.id = f"$event:{target.__name__}"
        self.target = target
        self.gather: Callable[[T], Awaitable[Mapping[str, Any]]] = supplier or _supplier
        if hasattr(target, "gather"):
            self.gather = _gather
        self.event_queue = Queue(queue_size)
        self.validate = (lambda x: generic_isinstance(x, target)) if is_typed_dict(target) else (lambda x: isinstance(x, target))
        _publishers[self.id] = self

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


def filter_publisher(target: type[T]) -> Publisher[T] | None:
    if (label := getattr(target, "__publisher__", f"$event:{target.__name__}")) in _publishers:
        return _publishers[label]
    return next((pub for pub in _publishers.values() if pub.target is target), None)


def search_publisher(event: T) -> Publisher[T] | None:
    if pub := _publishers.get(getattr(event, "__publisher__", f"$event:{type(event).__name__}")):
        return pub
    return next((pub for pub in _publishers.values() if pub.validate(event)), None)


def define(
    target: type[T],
    supplier: Callable[[T], Awaitable[Mapping[str, Any]]] | None = None,
    name: str | None = None,
) -> Publisher[T]:
    if name and name in _publishers:
        return _publishers[name]
    if (_id := getattr(target, "__publisher__", f"$event:{target.__name__}")) in _publishers:
        return _publishers[_id]
    return Publisher(target, name or _id, supplier)


def gather(target: type[T]):
    def wrapper(func: Callable[[T], Awaitable[Mapping[str, Any]]]):
        pub = filter_publisher(target) or define(target)
        pub.gather = func
        return func

    return wrapper
