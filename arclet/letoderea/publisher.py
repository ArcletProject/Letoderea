from __future__ import annotations

from typing import Any
from .subscriber import Subscriber
from .event import BaseEvent
from .context import system_ctx


class Publisher:
    id: str
    subscribers: dict[str, list[Subscriber]]
    supported_events: set[str]

    def __init__(self, *events: str):
        if not hasattr(self, "id"):
            raise TypeError("Publisher must have an id")
        self.subscribers = {}
        self.supported_events = set(events)

    @property
    def events(self) -> set[str]:
        return self.supported_events

    @events.setter
    def events(self, add: type | str):
        self.supported_events.add(add.__name__ if isinstance(add, type) else add)

    async def publish(self, event: BaseEvent) -> Any:
        """主动提供事件方法， event system 被动接收"""
        return await system_ctx.get().publish(event, self)

    async def supply(self) -> BaseEvent | None:
        """被动提供事件方法， 由 event system 主动轮询"""
        return

    def add_subscriber(self, event: str, subscriber: Subscriber) -> None:
        """
        添加订阅者
        """
        if event not in self.supported_events:
            raise TypeError(f"Event {event} is not supported by {self}")
        self.subscribers.setdefault(event, []).append(subscriber)

    def remove_subscriber(self, event: str, subscriber: Subscriber) -> None:
        """
        移除订阅者
        """
        if event not in self.supported_events:
            raise TypeError(f"Event {event} is not supported by {self}")
        self.subscribers.setdefault(event, []).remove(subscriber)
        if not self.subscribers[event]:
            del self.subscribers[event]
