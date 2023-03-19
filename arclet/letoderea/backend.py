from __future__ import annotations

from typing import Any
from .event import BaseEvent
from .publisher import BasePublisher


class BackendPublisher(BasePublisher):
    def validate(self, data: dict[str, Any]) -> BaseEvent | None:
        pass

    async def publish(self, event: BaseEvent) -> None:
        pass

    async def supply(self) -> BaseEvent:
        pass

    def add_subscriber(self, event: str, subscriber) -> None:
        """
        添加订阅者
        """
        self.subscribers.setdefault(event, []).append(subscriber)

    def remove_subscriber(self, event: str, subscriber) -> None:
        """
        移除订阅者
        """
        self.subscribers.setdefault(event, []).remove(subscriber)
        if not self.subscribers[event]:
            del self.subscribers[event]
