from typing import Callable

from ..entities.auxiliary import BaseAuxiliary
from ..entities.subscriber import Subscriber
from ..utils import ArgumentPackage
from ..handler import await_exec_target


class Depend(BaseAuxiliary):
    target: Subscriber

    def __init__(self, callable_func: Callable):
        self.target = Subscriber(callable_func)
        super().__init__()


@Depend.inject_aux("parsing", "supply")
async def depend(target_argument: ArgumentPackage[Depend]):
    return await await_exec_target(target_argument.source.target, target_argument.value)
