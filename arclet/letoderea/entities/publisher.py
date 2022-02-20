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
        将delegate添加到delegates中
        应当保证同priority同event的delegate只能有一个
        """
        ...

    def remove_delegate(self, target: Union[TEvent, EventDelegate]) -> None:
        ...

    def require(
            self,
            event: Union[str, TEvent],
            priority: Optional[int] = None,
            *args,
            **kwargs
    ) -> Optional[Union[EventDelegate, List[EventDelegate]]]:
        """
        依据event名称或者event对象，返回对应的delegate
        在每个publisher中可以存在多个delegate，利用priority进行排序
        但是同priority同event的delegate只能有一个
        """
        ...
