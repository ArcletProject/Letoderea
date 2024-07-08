from dataclasses import dataclass
from typing import Any

from ..auxiliary import AuxType, BaseAuxiliary, Scope, Interface
from ..handler import depend_handler
from ..subscriber import Subscriber
from ..typing import TTarget


@dataclass(init=False, eq=True)
class Depend(BaseAuxiliary):
    @property
    def scopes(self):
        return {Scope.parsing}

    async def __call__(self, scope: Scope, interface: Interface):
        sub = Subscriber(self.target, providers=interface.providers)  # type: ignore
        return await depend_handler(sub, source=interface.ctx, inner=True)

    target: TTarget[Any]

    def __init__(self, callable_func: TTarget[Any]):
        self.target = callable_func
        super().__init__(AuxType.depend)


def Depends(target: TTarget[Any]) -> Any:
    return Depend(target)
