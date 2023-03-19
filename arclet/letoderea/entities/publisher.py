from typing import List, Protocol, Union, Optional
from .delegate import EventDelegate
from ..utils import TEvent


class Publisher(Protocol):
    primary_event_delegate: EventDelegate
    delegates: List[EventDelegate]

    def set_primary_delegate(self, delegate: EventDelegate) -> None:
        ...

    def add_delegate(self, delegate: EventDelegate) -> None:
        """
        将 delegate 添加到 delegates 中
        应当保证同 priority 同 event 的 delegate 只能有一个
        """
        ...

    def remove_delegate(self, target: Union[TEvent, EventDelegate]) -> None:
        ...

    def require(
        self, event: Union[str, TEvent], priority: Optional[int] = None, *args, **kwargs
    ) -> Optional[Union[EventDelegate, List[EventDelegate]]]:
        """
        依据 event 名称或者 event 对象，返回对应的 delegate
        在每个 publisher 中可以存在多个 delegate，利用 priority 进行排序
        但是同 priority 同 event 的 delegate 只能有一个
        """
        ...
