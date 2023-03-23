from dataclasses import dataclass
from typing import Any

from ..auxiliary import SCOPE, AuxType, BaseAuxiliary
from ..handler import depend_handler
from ..subscriber import Subscriber
from ..typing import Contexts, TTarget


@dataclass(init=False, eq=True)
class Depend(BaseAuxiliary):
    @property
    def available_scopes(self):
        return {"parsing"}

    async def __call__(self, scope: SCOPE, context: Contexts):
        sub = Subscriber(self.target, providers=context["$subscriber"].providers)
        return await depend_handler(sub, context["event"])

    target: TTarget[Any]

    def __init__(self, callable_func: TTarget[Any]):
        self.target = callable_func
        super().__init__(AuxType.depend)


def Depends(target: TTarget[Any]) -> Any:
    return Depend(target)
