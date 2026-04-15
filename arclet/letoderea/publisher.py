from __future__ import annotations

from asyncio import Queue
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Generic, TypeVar, get_type_hints, overload
from typing_extensions import Self

from tarina.generic import generic_isinstance, is_typed_dict

from .context import Contexts
from .provider import Provider, ProviderFactory, get_providers

if TYPE_CHECKING:
    from .subscriber import Subscriber

T = TypeVar("T", covariant=True)
T1 = TypeVar("T1")
_publishers: dict[str, Publisher] = {}
_custom_validates: set[str] = set()
_static_validates: set[str] = set()
_publisher_cache: dict[type, list[str]] = {}


async def _supplier(event: Any, context: Contexts):
    if isinstance(event, dict):
        return context.update(event)
    return context.update({k: v for k, v in vars(event).items() if not k.startswith("_")})


class Publisher(Generic[T]):
    id: str
    validate: Callable[[Any], bool]

    def __init__(self, target: type[T], id_: str | None = None, supplier: Callable[[T, Contexts], Awaitable[Contexts | None]] | None = None, validator: Callable[[T], bool] | None = None, queue_size: int = -1):
        self.providers: list[Provider | ProviderFactory] = get_providers(target)
        if not isinstance(target, type) and not id_:  # pragma: no cover
            raise TypeError("Publisher with generic type must have a name")
        self.id = id_ or getattr(target, "__publisher__", f"$event:{target.__module__}.{target.__name__}")
        self.target = target
        self.supplier: Callable[[T, Contexts], Awaitable[Contexts | None]] = supplier or _supplier
        if hasattr(target, "gather"):
            self.supplier = target.gather  # type: ignore
        self.event_queue = Queue(queue_size)
        basic_validate = (
            (lambda x: generic_isinstance(x, target))
            if is_typed_dict(target) or not isinstance(target, type)
            else (lambda x: isinstance(x, target))
        )
        if validator:
            self.validate = lambda x: basic_validate(x) and validator(x)
            _custom_validates.add(self.id)
        elif not hasattr(self, "validate"):
            self.validate = basic_validate
            _static_validates.add(self.id)
        else:
            _custom_validates.add(self.id)
        _publishers[self.id] = self

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
        static_pubs = {id_: _publishers[id_] for id_ in _publisher_cache[t]}
    else:
        static_pubs = {id_: pub for id_, pub in _publishers.items() if id_ in _static_validates and pub.validate(event)}
        if static_pubs:
            _publisher_cache[t] = list(static_pubs.keys())
    if _custom_validates:
        dynamic_pubs = {id_: pub for id_, pub in _publishers.items() if id_ in _custom_validates and pub.validate(event)}
        return static_pubs | dynamic_pubs
    return static_pubs


@overload
def define(target: type[T1], supplier: Callable[[T1, Contexts], Awaitable[Contexts | None]] | None = None, validator: Callable[[T1], bool] | None = None, *, name: str | None = None) -> Publisher[T1]: ...


@overload
def define(*, name: str | None = None) -> Callable[[Callable[[T1], bool]], Publisher[T1]]: ...


def define(target: type | None = None, supplier: Callable[[Any, Contexts], Awaitable[Contexts | None]] | None = None, validator: Callable[[Any], bool] | None = None, *, name: str | None = None):
    if target is None:
        def wrapper(func: Callable[[T1], bool], /) -> Publisher[T1]:
            nonlocal name
            _target: type[T1] = next(iter(get_type_hints(func).values()))  # type: ignore
            if (pub := filter_publisher(_target)) and (not name or name == pub.id):  # pragma: no cover
                raise ValueError(f"Publisher for type {_target} already exists with id '{pub.id}'")
            return define(_target, validator=func, name=name)

        return wrapper

    if name and name in _publishers:
        return _publishers[name]
    if (_id := getattr(target, "__publisher__", f"$event:{target.__module__}.{target.__name__}")) in _publishers:
        return _publishers[_id]
    return Publisher(target, name, supplier, validator)


def gather(func: Callable[[Any, Contexts], Awaitable[Contexts | None]]):
    target: type[T1] = next(iter(get_type_hints(func).values()))  # type: ignore
    pub = filter_publisher(target) or define(target)
    pub.supplier = func
    return func
