from __future__ import annotations

from asyncio import Queue
from typing import TYPE_CHECKING, Any, Generic, TypeVar, get_type_hints
from collections.abc import Callable, Awaitable
from typing_extensions import Self
from tarina.generic import is_typed_dict, generic_isinstance

from .provider import Provider, ProviderFactory, get_providers
from .typing import Contexts

if TYPE_CHECKING:
    from .subscriber import Subscriber

T = TypeVar("T", covariant=True)
T1 = TypeVar("T1")
_publishers: dict[str, Publisher] = {}
_publisher_cache: dict[type, list[str]] = {}
_publisher_cache_ignore = set()


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

    def declare_cache_ignore(self):
        """声明该 Publisher 不适合被缓存，通常是因为其 validate 方法过于复杂或不稳定"""
        _publisher_cache_ignore.add(self.__class__)

    def gather(self, func: Callable[[T, Contexts], Awaitable[Contexts | None]]):
        self.supplier = func
        return func

    def __repr__(self):
        return f"{self.__class__.__name__}::{self.id}"

    def unsafe_push(self: Publisher[T1], event: T1) -> None:
        """将事件放入队列，等待被 event system 主动轮询; 该方法可能引发 QueueFull 异常"""
        self.event_queue.put_nowait(event)

    async def push(self: Publisher[T1], event: T1):
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
    ) -> None:  # pragma: no cover
        """移除间接 Provider"""
        idx = [i for i, p in enumerate(self.providers) if (isinstance(arg, (ProviderFactory, Provider)) and p == arg) or (isinstance(arg, type) and isinstance(p, arg))]
        for i in reversed(idx):
            self.providers.pop(i)

    def check(self: Self, func: Callable[[Self, Subscriber], bool]):
        self.check_subscriber = func.__get__(self)  # type: ignore
        return func

    def check_subscriber(self, sub: Subscriber) -> bool:
        """检查 Subscriber 是否可以订阅该 Publisher

        默认总是返回 True, 可重写该方法以实现更复杂的逻辑
        """
        return True


def filter_publisher(target: type[T1]) -> Publisher[T1] | None:
    if (label := getattr(target, "__publisher__", f"$event:{target.__module__}.{target.__name__}")) in _publishers:
        return _publishers[label]
    return next((pub for pub in _publishers.values() if pub.target == target), None)


def get_publishers(event: Any) -> dict[str, Publisher]:
    t = event.__class__
    if t in _publisher_cache:
        return {id_: _publishers[id_] for id_ in _publisher_cache[t]}
    pubs = {pub.id: pub for pub in _publishers.values() if pub.validate(event)}
    if cached := [pub.id for pub in pubs.values() if pub.__class__ not in _publisher_cache_ignore]:
        _publisher_cache[t] = cached
    return pubs


def define(
    target: type[T1],
    supplier: Callable[[T1, Contexts], Awaitable[Contexts | None]] | None = None,
    name: str | None = None,
) -> Publisher[T1]:
    if name and name in _publishers:
        return _publishers[name]
    if (_id := getattr(target, "__publisher__", f"$event:{target.__module__}.{target.__name__}")) in _publishers:
        return _publishers[_id]
    return Publisher(target, name, supplier)


def gather(func: Callable[[Any, Contexts], Awaitable[Contexts | None]]):
    target: type[T1] = next(iter(get_type_hints(func).values()))  # type: ignore
    pub = filter_publisher(target) or define(target)
    pub.supplier = func
    return func
