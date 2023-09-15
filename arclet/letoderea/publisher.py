from __future__ import annotations

from abc import ABCMeta, abstractmethod
from asyncio import Queue
from contextlib import suppress, contextmanager
from typing import Any, Callable, ContextManager

from .event import BaseEvent
from .provider import Provider
from .subscriber import Subscriber
from .handler import dispatch
from .context import publisher_ctx


class Publisher(metaclass=ABCMeta):
    id: str
    subscribers: list[Subscriber]
    providers: list[Provider]

    def __init__(self, id_: str, queue_size: int = -1):
        self.id = id_
        self.event_queue = Queue(queue_size)
        self.subscribers = []
        self.providers = []

    def __repr__(self):
        return f"Publisher::{self.id}"


    @abstractmethod
    def validate(self, event: type[BaseEvent] | BaseEvent):
        """验证该事件类型是否符合该发布者"""
        raise NotImplementedError

    async def publish(self, event: BaseEvent) -> Any:
        """主动向自己的订阅者发布事件"""
        await dispatch(self.subscribers, event)

    def unsafe_push(self, event: BaseEvent) -> None:
        """将事件放入队列，等待被 event system 主动轮询; 该方法可能引发 QueueFull 异常"""
        self.event_queue.put_nowait(event)

    async def push(self, event: BaseEvent):
        """将事件放入队列，等待被 event system 主动轮询"""
        await self.event_queue.put(event)

    async def supply(self) -> BaseEvent | None:
        """被动提供事件方法， 由 event system 主动轮询"""
        return await self.event_queue.get()

    def add_subscriber(self, subscriber: Subscriber) -> None:
        """
        添加订阅者
        """
        self.subscribers.append(subscriber)

    def remove_subscriber(self, subscriber: Subscriber) -> None:
        """
        移除订阅者
        """
        with suppress(ValueError):
            self.subscribers.remove(subscriber)

    def add_provider(self,  *providers: Provider) -> None:
        """为发布器增加间接 Provider"""
        self.providers.extend(providers)

    def unbind_provider(self, provider: Provider) -> None:
        """移除发布器的间接 Provider"""
        with suppress(ValueError):
            self.providers.remove(provider)

    @contextmanager
    def context(self):
        token = publisher_ctx.set(self)
        yield self
        publisher_ctx.reset(token)


def accept(
    name: str,
    *events: type[BaseEvent],
    predicate: Callable[[type[BaseEvent] | BaseEvent], bool] | None = None
):
    """依据给定的事件类型或者事件类型的谓词，生成一个发布者"""
    if predicate is None and not events:
        raise ValueError("events and predicate cannot be both None")

    if predicate is None:
        _predicate = lambda event: event in events or isinstance(event, events)
    elif not events:
        _predicate = predicate
    else:
        _predicate = lambda event: predicate(event) and (event in events or isinstance(event, events))

    class GeneratedPublisher(Publisher):
        def validate(self, event: type[BaseEvent] | BaseEvent):
            return _predicate(event)

    return GeneratedPublisher(f"{name}::{_predicate}")
