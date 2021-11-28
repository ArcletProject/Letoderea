from typing import Callable, Optional, List
from .decorator import TemplateDecorator
from ..utils import argument_analysis


class SubscriberInterface:
    callable_target: Callable


class Subscriber(SubscriberInterface):
    def __init__(
            self,
            callable_target: Callable,
            *,
            subscriber_name: Optional[str] = None,
            decorators: Optional[List[TemplateDecorator]] = None
    ) -> None:
        self.callable_target = callable_target
        self.subscriber_name = subscriber_name or callable_target.__name__
        self.decorators = decorators

    def __call__(self, *args, **kwargs):
        return self.callable_target(*args, **kwargs)

    def __repr__(self):
        return f'<Subscriber,name={self.subscriber_name}>'

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        if isinstance(other, Subscriber):
            return other.name == self.subscriber_name
        elif isinstance(other, str):
            return other == self.subscriber_name

    @property
    def name(self):
        return self.subscriber_name

    @name.setter
    def name(self, new_name):
        self.subscriber_name = new_name

    @property
    def params(self):
        return argument_analysis(self.callable_target)

    @staticmethod
    def set(
            subscriber_name: Optional[str] = None,
            priority: int = 16,
            decorators: List[TemplateDecorator] = None
    ):
        """该方法生成一个订阅器实例，该订阅器负责调控装饰的可执行函数

        若订阅器的注册事件是消息链相关的，可预先根据写入的命令相关参数进行判别是否执行该订阅器装饰的函数

        若不填如下参数则表示接受任意形式的命令

        Args:
            subscriber_name :装饰器名字，可选
            priority: 优先级，默认为最高
            decorators: 装饰器列表，可选
        """

        def wrapper(func):
            subscriber = Subscriber(
                func,
                subscriber_name=subscriber_name,
                decorators=decorators
            )
            return subscriber

        return wrapper

    subscriber_name: Optional[str]
    decorators: Optional[List[TemplateDecorator]]
