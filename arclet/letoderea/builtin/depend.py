from typing import Callable

from ..entities.auxiliary import BaseAuxiliary
from ..entities.subscriber import Subscriber
from ..utils import ArgumentPackage
from ..handler import await_exec_target


class Depend(BaseAuxiliary):
    target: Subscriber

    def __init__(self, callable_func: Callable):
        self.target = Subscriber(callable_func)

        @self.set_aux("parsing", "supply")
        async def depend(target_argument: ArgumentPackage):
            return await await_exec_target(self.target, target_argument.value)
