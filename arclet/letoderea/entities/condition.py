from abc import ABC, abstractmethod
from typing import overload, Callable


class TemplateCondition(ABC):
    """
    条件基类, 用于事件发生时判断是否响应
    """
    judge: Callable[[], bool]

    @staticmethod
    @overload
    @abstractmethod
    def judge() -> bool:
        ...

    @classmethod
    @overload
    @abstractmethod
    def judge(cls) -> bool:
        ...

    @abstractmethod
    def judge(self) -> bool:
        """外部方法,用于判断该条件是否成立并返回结果; 该方法可以是 `stasticmethod`,`classmethod` 亦或是普通的方法/函数.
        唯一的要求是返回值必须为一布尔值
        """
        pass

    def __eq__(self, other: "TemplateCondition"):
        return self.__annotations__ == other.__annotations__
