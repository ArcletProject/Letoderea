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
        将delegate添加到delegates中
        应当保证同priority同event的delegate只能有一个
        """
        if not self.delegates:
            self.delegates.append(delegate)
        else:
            last_delegate = self.delegates[-1]
            if last_delegate.bind_event == delegate.bind_event:
                if last_delegate.priority == delegate.priority:
                    return
            self.delegates.append(delegate)

    def remove_delegate(self, target: Union[TEvent, EventDelegate]) -> None:
        if isinstance(target, EventDelegate):
            self.delegates.remove(target)
        else:
            delegates = self.require(target)
            for delegate in delegates:
                self.delegates.remove(delegate)

    def require(
            self,
            event: Union[str, TEvent],
            priority: Optional[int] = None,
    ) -> Optional[Union[EventDelegate, List[EventDelegate]]]:
        """
        依据event名称或者event对象，返回对应的delegate
        在每个publisher中可以存在多个delegate，利用priority进行排序
        但是同priority同event的delegate只能有一个
        """
        _delegates = []
        for delegate in self.delegates:
            if delegate.bind_event == event:
                _delegates.append(delegate)
        if len(_delegates) == 0:
            return None
        if priority:
            for delegate in filter(lambda d: d.priority == priority, _delegates):
                return delegate
        return _delegates
