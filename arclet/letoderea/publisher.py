from __future__ import annotations

from typing import Any
from abc import abstractmethod, ABCMeta
from .subscriber import Subscriber
from .event import BaseEvent


class BasePublisher(metaclass=ABCMeta):
    subscribers: dict[str, list[Subscriber]]
    supported_events: set[str]

    def __init__(self, *events: str):
        self.subscribers = {}
        self.supported_events = set(events)

    @property
    def events(self) -> set[str]:
        return self.supported_events

    @events.setter
    def events(self, add: type | str):
        self.supported_events.add(add.__name__ if isinstance(add, type) else add)

    @abstractmethod
    def validate(self, data: dict[str, Any]) -> BaseEvent | None:
        """
        验证事件数据是否为该 Publisher 所属
        """
        raise NotImplementedError

    @abstractmethod
    async def publish(self, event: BaseEvent) -> None:
        """主动提供事件方法， event system 被动接收"""
        raise NotImplementedError

    @abstractmethod
    async def supply(self) -> BaseEvent:
        """被动提供事件方法， 由 event system 主动轮询"""
        raise NotImplementedError

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
