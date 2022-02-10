from typing import Callable, Coroutine

from .entities.decorator import TemplateDecorator
from .entities.subscriber import Subscriber
from .utils import ArgumentPackage
from .handler import await_exec_target


class Depend(TemplateDecorator):
    target: Subscriber

    def __init__(self, callable_func: Callable):
        super().__init__(keep=False)
        self.target = Subscriber(callable_func)

    def supply(self, target_argument: ArgumentPackage) -> Coroutine:
        coro = await_exec_target(self.target, target_argument.value)
        return coro
