from typing import Any, overload, List, Optional
from ..utils import ArgumentPackage
from abc import ABC, abstractmethod


class TemplateDecorator(ABC):
    """
    参数装饰器基类，用于修饰函数或事件

    Args:
        keep: 是否保留未装饰的参数,若为False则会覆盖原有参数
    """

    __disable__: List[str] = ""

    keep: bool = True
    may_target_type: type

    def __init__(self, target_type: Optional[type] = None, keep: bool = True):
        """
            参数装饰器基类，用于修饰函数或事件

            Args:
                target_type: 可能的目标参数类型,若填入则装饰器只接受该类型的参数
                keep: 是否保留未装饰的参数,若为False则会覆盖原有参数
            """
        self.may_target_type = target_type
        self.keep = keep

    def supply_wrapper(self, args_name: str, args_value: Any):
        result = self.supply(ArgumentPackage(args_name, args_value.__class__, args_value))
        if result is None:
            return
        if not self.keep:
            return {args_name: result}
        return {result.__class__.__name__: result}

    @staticmethod
    @abstractmethod
    @overload
    def supply(target_argument: ArgumentPackage) -> Any:
        ...

    @abstractmethod
    def supply(self, target_argument: ArgumentPackage) -> Any:
        """在回调函数的参数被解析后调用, 用于修饰函数的参数

        Args:
            target_argument: 一个保存了参数名、参数注解与参数内容的类
        Returns:
            装饰后的值
        """


class EventDecorator(TemplateDecorator):
    __disable__ = 'after_parser'

    @abstractmethod
    def supply(self, target_argument: ArgumentPackage) -> Any:
        return target_argument.value


class ArgsDecorator(TemplateDecorator):
    __disable__ = 'before_parser'

    @abstractmethod
    def supply(self, target_argument: ArgumentPackage) -> Any:
        return target_argument.value
