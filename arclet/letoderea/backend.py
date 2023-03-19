from __future__ import annotations

from .publisher import Publisher


class BackendPublisher(Publisher):
    id = "__backend__publisher__"

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
