from __future__ import annotations

import functools
import inspect
import sys
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar
from typing_extensions import ParamSpec

from tarina import generic_isinstance

from .context import Contexts
from .decorate import propagate
from .exceptions import BLOCK, STOP, ExceptionHandler, InnerHandlerException, UnresolvedRequirement, _ExitException
from .subscriber import STACK, CompileParam, Propagator, Subscriber, current_subscriber
from .typing import TCallable

T = TypeVar("T")
P = ParamSpec("P")


if sys.version_info >= (3, 11):  # pragma: no cover
    from typing import get_overloads
    from typing import overload as overload  # noqa: F401
else:  # pragma: no cover
    _overload_registry = defaultdict(functools.partial(defaultdict, dict))


    def _overload_dummy(*args, **kwds):
        """Helper for @overload to raise when called."""
        raise NotImplementedError(
            "You should not call an overloaded function. "
            "A series of @overload-decorated functions "
            "outside a stub module should always be followed "
            "by an implementation that is not @overload-ed.")

    if TYPE_CHECKING:
        from typing import overload as overload
    else:
        def overload(func):
            # classmethod and staticmethod
            f = getattr(func, "__func__", func)
            try:
                _overload_registry[f.__module__][f.__qualname__][f.__code__.co_firstlineno] = func  # type: ignore
            except AttributeError:
                # Not a normal function; ignore.
                pass
            return _overload_dummy


    def get_overloads(func):
        """Return all defined overloads for *func* as a sequence."""
        # classmethod and staticmethod
        f = getattr(func, "__func__", func)
        if f.__module__ not in _overload_registry:
            return []
        mod_dict = _overload_registry[f.__module__]
        if f.__qualname__ not in mod_dict:
            return []
        return list(mod_dict[f.__qualname__].values())


class Overloads(Propagator):
    def __init__(self):
        self.funcs: list[Subscriber] = []
        self.allow_empty: dict[str, bool] = {}
        self.funcs_params: dict[str, dict[Any, tuple[CompileParam, int]]] = {}
        self.names_index: dict[str, set[int]] = {}
        self.impl_params: list[CompileParam] = []

    def validate(self, subscriber: Subscriber) -> bool:
        overloads = get_overloads(subscriber.callable_target)
        if not overloads or len(overloads) == 1:
            raise TypeError("No overloads found for the function.")
        self.impl_params.extend(subscriber.params)
        names_list = []
        for i, func in enumerate(overloads):
            sub = Subscriber(
                func,
                providers=subscriber.providers,
                skip_req_missing=False
            )
            self.funcs.append(sub)
            names_list.append(set(param.name for param in sub.params))
            for param in sub.params:
                if param.name not in self.names_index:
                    self.names_index[param.name] = set()
                self.names_index[param.name].add(i)
                if param.name not in self.funcs_params:
                    self.funcs_params[param.name] = {}
                if param.annotation not in self.funcs_params[param.name]:
                    self.funcs_params[param.name][param.annotation] = (param, i)
        if set(self.funcs_params.keys()) - set(param.name for param in self.impl_params):
            # 实现函数的参数必须包含所有重载函数的参数
            raise TypeError("Implementation function must contain all parameters of overloads.")
        for param in self.impl_params:
            self.allow_empty[param.name] = any(param.name not in names for names in names_list)
        setattr(subscriber, "__overload_source__", subscriber.callable_target)
        subscriber.callable_target = self.execute
        subscriber._recompile()
        subscriber._attach_disposes(lambda _: self.dispose())
        return False

    def dispose(self):
        self.funcs.clear()
        self.allow_empty.clear()
        self.funcs_params.clear()
        self.names_index.clear()
        self.impl_params.clear()

    async def _solve(self, context: Contexts, param: CompileParam):
        if param.depend:
            dep_res = await param.depend(context)
            if dep_res is STOP or dep_res is BLOCK:  # pragma: no cover
                raise UnresolvedRequirement(f"Failed to resolve parameter {param.name} for overloads.")
            return dep_res
        res = await param.solve(context)
        if res is STOP or res is BLOCK:  # pragma: no cover
            raise UnresolvedRequirement(f"Failed to resolve parameter {param.name} for overloads.")
        return res

    async def execute(self, context: Contexts):
        arguments: Contexts = {}  # type: ignore
        choice: int = 0
        for param in self.impl_params:
            if param.name not in self.funcs_params:
                continue
            ans = None
            for anno, (params, index) in self.funcs_params[param.name].items():
                ans = await self._solve(context, params)
                if not generic_isinstance(ans, anno):
                    continue
                if index not in self.names_index[param.name]:  # pragma: no cover
                    continue
                arguments[param.name] = ans
                choice = index
                break
            else:
                if ans is not None or not self.allow_empty[param.name]:
                    raise UnresolvedRequirement(f"Failed to resolve parameter {param.name!r} for overloads.")
        func = self.funcs[choice]
        token = current_subscriber.set(func)

        try:
            if func.is_cm:  # pragma: no cover
                stack = context[STACK]
                result = await stack.enter_async_context(func._callable_target(**arguments))
            elif func.is_agen:  # pragma: no cover
                result = func._callable_target(**arguments)
            else:
                result = await func._callable_target(**arguments)
        except InnerHandlerException:  # pragma: no cover
            raise
        except Exception as e:  # pragma: no cover
            if isinstance(e, _ExitException):
                return e
            raise ExceptionHandler.call(e, func.callable_target, context, True) from e
        finally:
            current_subscriber.reset(token)  # type: ignore
        return result

    def compose(self):  # pragma: no cover
        yield self.execute


def apply_overload(func: TCallable) -> TCallable:
    return propagate(Overloads())(func)


async def call_overload(func: Callable[P, Awaitable[T]] | Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    assert isinstance(func, Subscriber) and hasattr(func, "__overload_source__"), "Function must be decorated with @apply_overload."
    source = getattr(func, "__overload_source__")
    bind = inspect.signature(source).bind(*args, **kwargs)
    bind.apply_defaults()
    context = dict(bind.arguments)
    return await func.callable_target(context)  # type: ignore
