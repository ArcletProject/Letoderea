from dataclasses import dataclass, field
from typing import Callable, Any, Literal, List, Union, Dict, TYPE_CHECKING, Type
from ..utils import ArgumentPackage, run_always_await
from .event import TemplateEvent
from ..exceptions import JudgementError

if TYPE_CHECKING:
    from .subscriber import Subscriber

scopes = Literal["before_parse", "parsing", "after_parse", "execution_complete"]
aux_types = Literal["judge", "supply"]
supply = Callable[[ArgumentPackage], Any]
judge = Callable[["BaseAuxiliary", TemplateEvent], bool]


@dataclass
class _AuxHandler:
    """
    参数辅助器基类，用于修饰参数, 或者判断条件

    Argument:
        keep: 是否保留未装饰的参数,若为False则会覆盖原有参数
    """

    scope: scopes
    aux_type: aux_types
    handler: Union[supply, judge]
    keep: bool = field(default=False)

    async def supply_wrapper_keep(
        self, source: "BaseAuxiliary", arg_type: type, args: Dict[str, Any]
    ):
        h: supply = self.handler
        result = {}
        for k, v in args.items():
            arg = await run_always_await(h, ArgumentPackage(source, k, arg_type, v))
            if arg is None:
                continue
            type_arg = type(arg)
            if type_arg is not arg_type:
                result[arg.__class__] = {k: arg}
        return result

    async def supply_wrapper(
        self, source: "BaseAuxiliary", arg_type: type, args: Dict[str, Any]
    ):
        h: supply = self.handler
        result = {}
        for k, v in args.items():
            arg = await run_always_await(h, ArgumentPackage(source, k, arg_type, v))
            if arg is None:
                continue
            result[k] = arg
        return result or args

    async def judge_wrapper(self, source: "BaseAuxiliary", event: TemplateEvent):
        h: judge = self.handler
        if await run_always_await(h, source, event) is False:
            raise JudgementError


def _validate(atype: str):
    if atype == "supply":
        return supply
    if atype == "judge":
        return judge
    raise ValueError(f"Invalid auxiliary type: {atype}")


class BaseAuxiliary:
    local_storage: Dict[Type["BaseAuxiliary"], Dict[scopes, List[_AuxHandler]]] = {}
    aux_handlers: Dict[scopes, List[_AuxHandler]]

    def __init__(self):
        self.aux_handlers = {}
        if self.local_storage.get(self.__class__):
            self.aux_handlers.update(self.local_storage.pop(self.__class__))

    def set_aux(self, scope: scopes, atype: aux_types, keep: bool = False):
        _func_type = _validate(atype)

        def decorator(func: _func_type):
            if scope not in self.aux_handlers:
                self.aux_handlers[scope] = []
            self.aux_handlers[scope].append(_AuxHandler(scope, atype, func, keep))
            return func

        return decorator

    @classmethod
    def inject_aux(cls, scope: scopes, atype: aux_types, keep: bool = False):
        _func_type = _validate(atype)

        def decorator(func: _func_type):
            if cls not in cls.local_storage:
                cls.local_storage[cls] = {}
            if scope not in cls.local_storage[cls]:
                cls.local_storage[cls][scope] = []
            cls.local_storage[cls][scope].append(_AuxHandler(scope, atype, func, keep))
            return func

        return decorator

    @classmethod
    def set_target(cls, *args, **kwargs):
        def __wrapper(target: Union[Callable, "Subscriber"]):
            if isinstance(target, Callable):
                if not hasattr(target, "__auxiliaries__"):
                    setattr(target, "__auxiliaries__", [cls(*args, **kwargs)])  # type: ignore
                else:
                    getattr(target, "__auxiliaries__").append(cls(*args, **kwargs))  # type: ignore
            else:
                target.auxiliaries.append(cls(*args, **kwargs))  # type: ignore
            return target

        return __wrapper

    def __eq__(self, other: "BaseAuxiliary"):
        return self.aux_handlers == other.aux_handlers
