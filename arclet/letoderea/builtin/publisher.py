from typing import List, Union, Optional
from ..entities.delegate import EventDelegate
from ..utils import TEvent


class TemplatePublisher:
    primary_event_delegate: EventDelegate
    delegates: List[EventDelegate]

    def __init__(self):
        self.delegates = []

    def set_primary_delegate(self, delegate: EventDelegate) -> None:
        self.primary_event_delegate = delegate

    def add_delegate(self, delegate: EventDelegate) -> None:
        """
        将 delegate 添加到 delegates 中
        应当保证同 priority 同 event 的 delegate 只能有一个
        """
        if self.delegates:
            last_delegate = self.delegates[-1]
            if (
                last_delegate.bind_event == delegate.bind_event
                and last_delegate.priority == delegate.priority
            ):
                return
        self.delegates.append(delegate)

    def remove_delegate(self, target: Union[TEvent, EventDelegate]) -> None:
        if isinstance(target, EventDelegate):
            self.delegates.remove(target)
        elif delegates := self.require(target):
            for delegate in delegates:
                self.delegates.remove(delegate)

    def require(
        self,
        event: Union[str, TEvent],
        priority: Optional[int] = None,
    ) -> Optional[Union[EventDelegate, List[EventDelegate]]]:
        """
        依据 event 名称或者 event 对象，返回对应的 delegate
        在每个 publisher 中可以存在多个 delegate，利用 priority 进行排序
        但是同 priority 同 event 的 delegate 只能有一个
        """
        _delegates = [
            delegate for delegate in self.delegates if delegate.bind_event == event
        ]
        if not _delegates:
            return
        if priority:
            for delegate in filter(lambda d: d.priority == priority, _delegates):
                return delegate
        return _delegates
