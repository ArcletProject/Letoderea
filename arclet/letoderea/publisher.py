from __future__ import annotations

from asyncio import Queue
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from .context import system_ctx
from .event import BaseEvent
from .provider import Provider
from .subscriber import Subscriber


@dataclass
class Delegate:
    etype: type[BaseEvent]
    publisher: Publisher

    def __add__(self, other):
        if isinstance(other, Subscriber):
            self.publisher.add_subscriber(self.etype, other)  # type: ignore
        elif isinstance(other, Provider):
            self.publisher.bind_provider(self.etype, other)  # type: ignore
        else:
            raise TypeError(f"unsupported operand type(s) for +: '{type(self).__name__}' and '{type(other).__name__}'")
        return self

    def __iadd__(self, other):
        if isinstance(other, Subscriber):
            self.publisher.add_subscriber(self.etype, other)  # type: ignore
        elif isinstance(other, Provider):
            self.publisher.bind_provider(self.etype, other)  # type: ignore
        else:
            raise TypeError(f"unsupported operand type(s) for +: '{type(self).__name__}' and '{type(other).__name__}'")
        return self

    def __sub__(self, other):
        if isinstance(other, Subscriber):
            self.publisher.remove_subscriber(self.etype, other)  # type: ignore
        elif isinstance(other, Provider):
            self.publisher.unbind_provider(self.etype, other)  # type: ignore
        else:
            raise TypeError(f"unsupported operand type(s) for -: '{type(self).__name__}' and '{type(other).__name__}'")
        return self

    def __isub__(self, other):
        if isinstance(other, Subscriber):
            self.publisher.remove_subscriber(self.etype, other)  # type: ignore
        elif isinstance(other, Provider):
            self.publisher.unbind_provider(self.etype, other)  # type: ignore
        else:
            raise TypeError(f"unsupported operand type(s) for -: '{type(self).__name__}' and '{type(other).__name__}'")
        return self


class Publisher:
    id: str
    subscribers: dict[type[BaseEvent], list[Subscriber]]
    providers: dict[type[BaseEvent], list[Provider]]
    supported_events: set[type[BaseEvent]]

    def __init__(self, id_: str, *events: type[BaseEvent], queue_size: int = -1):
        self.id = id_
        self.event_queue = Queue(queue_size)
        self.subscribers = {}
        self.providers = {}
        self.supported_events = set(events)
        if es := system_ctx.get():
            es.add_publisher(self)

    def __repr__(self):
        return f"Publisher::{self.id}"

    @property
    def events(self) -> set[type[BaseEvent]]:
        return self.supported_events

    @events.setter
    def events(self, add: type[BaseEvent]):
        self.supported_events.add(add)

    async def publish(self, event: BaseEvent) -> Any:
        """主动提供事件方法， event system 被动接收"""
        return await system_ctx.get().publish(event, self)

    def unsafe_push(self, event: BaseEvent) -> None:
        """将事件放入队列，等待被 event system 主动轮询; 该方法可能引发 QueueFull 异常"""
        self.event_queue.put_nowait(event)

    async def push(self, event: BaseEvent):
        """将事件放入队列，等待被 event system 主动轮询"""
        await self.event_queue.put(event)

    async def supply(self) -> BaseEvent | None:
        """被动提供事件方法， 由 event system 主动轮询"""
        return await self.event_queue.get()

    def add_subscriber(self, event: type[BaseEvent], subscriber: Subscriber) -> None:
        """
        添加订阅者
        """
        if event not in self.supported_events:
            raise TypeError(f"Event {event} is not supported by {self}")
        self.subscribers.setdefault(event, []).append(subscriber)

    def remove_subscriber(self, event: type[BaseEvent], subscriber: Subscriber) -> None:
        """
        移除订阅者
        """
        if event not in self.supported_events:
            raise TypeError(f"Event {event} is not supported by {self}")
        with suppress(ValueError):
            self.subscribers.setdefault(event, []).remove(subscriber)
        if not self.subscribers[event]:
            del self.subscribers[event]

    def bind_provider(self, event: type[BaseEvent], *providers: Provider) -> None:
        """为事件绑定间接 Provider"""
        if event not in self.supported_events:
            raise TypeError(f"Event {event} is not supported by {self}")
        self.providers.setdefault(event, []).extend(providers)

    def unbind_provider(self, event: type[BaseEvent], provider: Provider) -> None:
        """移除事件的间接 Provider"""
        if event not in self.supported_events:
            raise TypeError(f"Event {event} is not supported by {self}")
        with suppress(ValueError):
            self.providers.setdefault(event, []).remove(provider)
        if not self.providers[event]:
            del self.providers[event]

    def __getitem__(self, item: type[BaseEvent]):
        if item not in self.supported_events:
            raise TypeError(f"Event {item} is not supported by {self}")
        return Delegate(etype=item, publisher=self)  # type: ignore

    def __setitem__(self, key, value):
        if key not in self.supported_events:
            raise TypeError(f"Event {key} is not supported by {self}")
        if isinstance(value, Subscriber):
            self.add_subscriber(key, value)
        elif isinstance(value, Provider):
            self.bind_provider(key, value)
