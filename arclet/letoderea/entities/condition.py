from abc import ABC, abstractmethod
from typing import overload, Callable
from .event import TemplateEvent


class TemplateCondition(ABC):
    """
    条件基类, 用于事件发生时判断是否响应
    """
    judge: Callable[[], bool]

    @staticmethod
    @overload
    @abstractmethod
    def judge(*args, **kwargs) -> bool:
        ...

    @classmethod
    @overload
    @abstractmethod
    def judge(cls, *args, **kwargs) -> bool:
        ...

    @abstractmethod
    def judge(self, *args, **kwargs) -> bool:
        """外部方法,用于判断该条件是否成立并返回结果; 该方法可以是 `stasticmethod`,`classmethod` 亦或是普通的方法/函数.
        唯一的要求是返回值必须为一布尔值
        """
        pass

    def __eq__(self, other: "TemplateCondition"):
        return self.__annotations__ == other.__annotations__


class EventCondition(TemplateCondition):

    @staticmethod
    @overload
    @abstractmethod
    def judge(event: TemplateEvent) -> bool:
        ...

    @classmethod
    @overload
    @abstractmethod
    def judge(cls, event: TemplateEvent) -> bool:
        ...

    def judge(self, event: TemplateEvent) -> bool:
        pass
