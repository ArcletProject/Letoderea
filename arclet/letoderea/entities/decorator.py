from typing import Type, Optional, Any, overload, List
from ..utils import ArgumentPackage


class TemplateDecorator:
    """
    参数装饰器基类，用于修饰函数或事件

    Args:
        target_type: 目标参数的类型
        supplement_type: 参数被装饰后的类型,通常与target_type一致
        keep: 是否保留未装饰的参数,若为False则会覆盖原有参数
    """
    target_type: Type
    supplement_type: Type
    keep: bool = True

    __disable__: List[str]

    def __init__(self, target_type: Type, supplement_type: Optional[Type] = None, keep: bool = True):
        self.target_type = target_type
        self.supplement_type = supplement_type or target_type
        self.keep = keep

    @staticmethod
    @overload
    def before_parser(target_argument: ArgumentPackage) -> Any:
        ...

    def before_parser(self, target_argument: ArgumentPackage) -> Any:
        """生命周期钩子: 在回调函数的参数被解析前被调用, 用于修饰事件的参数

        Args:
            target_argument: 一个保存了参数名、参数注解与参数内容的类
        Returns:
            装饰后的值,该值的类型应与supplement_type一致
        """
        return target_argument.value

    @staticmethod
    @overload
    def after_parser(target_argument: ArgumentPackage) -> Any:
        ...

    def after_parser(self, target_argument: ArgumentPackage) -> Any:
        """生命周期钩子: 在回调函数的参数被解析后被调用, 用于修饰函数的参数

        Args:
            target_argument: 一个保存了参数名、参数注解与参数内容的类
        Returns:
            装饰后的值,该值的类型应与supplement_type一致
        """
        return target_argument.value

    def __eq__(self, other: "TemplateDecorator"):
        return all([self.target_type == other.target_type, self.supplement_type == other.supplement_type])
