from typing import Callable, Any

from ..auxiliary import BaseAuxiliary, Scope, AuxType
from ..subscriber import Subscriber
from ..handler import depend_handler
from ..typing import Contexts, TTarget


class Depend(BaseAuxiliary):
    target: TTarget[Any]

    def __init__(self, callable_func: TTarget[Any]):
        self.target = callable_func
        super().__init__()
        self.set(Scope.parsing, AuxType.judge)


@Depend.inject(Scope.parsing, AuxType.supply)
async def depend(source: Depend, contexts: Contexts):
    sub = Subscriber(source.target, providers=contexts["$subscriber"].providers)
    return await depend_handler(sub, contexts["event"])


def Depends(target: TTarget[Any]) -> Any:
    return Depend(target)
