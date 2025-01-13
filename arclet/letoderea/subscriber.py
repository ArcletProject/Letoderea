from __future__ import annotations

import sys
import asyncio
from collections.abc import Awaitable, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Generic, TypeVar, cast, final
from typing_extensions import Self, get_args, get_origin, TypeAlias
from uuid import uuid4

from tarina import Empty, is_async, signatures

from .exceptions import InnerHandlerException, ParsingStop, UndefinedRequirement, exception_handler
from .provider import Param, Provider, ProviderFactory, provide
from .ref import Deref, generate
from .typing import CtxItem, Contexts, Force, TTarget, is_async_gen_callable, is_gen_callable, run_sync, \
    run_sync_generator, Result


TState: TypeAlias = dict[str, Any]


class ResultProvider(Provider[Any]):
    def validate(self, param: Param):
        return param.name == "result"

    async def __call__(self, context: Contexts):
        return context.get("$result")


class StateProvider(Provider[Any]):
    def validate(self, param: Param):
        return param.name == "state" and param.annotation == TState

    async def __call__(self, context: Contexts):
        return context[SUBSCRIBER]._state


@dataclass(init=False, eq=True)
class Depend:
    target: TTarget[Any]
    sub: Subscriber[Any]
    cache: bool = False

    def __init__(self, callable_func: TTarget[Any], cache: bool = False):
        self.target = callable_func
        self.cache = cache

    def init_subscriber(self, provider: list[Provider | ProviderFactory]):
        self.sub = Subscriber(self.target, providers=provider)
        return self


def Depends(target: TTarget[Any], cache: bool = False) -> Any:
    return Depend(target, cache)


@dataclass
class CompileParam:
    name: str
    annotation: Any
    default: Any
    providers: list[Provider]
    depend: Depend | None
    record: Provider | None

    __slots__ = ("name", "annotation", "default", "providers", "depend", "record")

    async def solve(self, context: Contexts | dict[str, Any]):
        if self.name in context:
            return context[self.name]
        if self.record and (res := await self.record(context)):  # type: ignore
            if res.__class__ is Force:
                res = res.value
            return res
        for _provider in self.providers:
            res = await _provider(context)  # type: ignore
            if res is None:
                continue
            if res.__class__ is Force:
                res = res.value
            self.record = _provider
            return res
        if self.default is not Empty:
            return self.default
        raise UndefinedRequirement(self.name, self.annotation, self.default, self.providers)


def _compile(target: Callable, providers: list[Provider | ProviderFactory]) -> list[CompileParam]:
    res = []
    for name, anno, default in signatures(target):
        param = CompileParam(name, anno, default, [], None, None)
        for _provider in providers:
            if isinstance(_provider, ProviderFactory):
                if result := _provider.validate(Param(name, anno, default, bool(param.providers))):
                    param.providers.append(result)
            elif _provider.validate(Param(name, anno, default, bool(param.providers))):
                param.providers.append(_provider)
        param.providers.sort(key=lambda x: x.priority)
        if get_origin(anno) is Annotated:
            org, *meta = get_args(anno)
            for m in reversed(meta):
                if isinstance(m, Provider):
                    param.providers.insert(0, m)
                elif isinstance(m, str):
                    param.providers.insert(0, provide(org, name, lambda x: x.get(m)))
                elif isinstance(m, Deref):
                    param.providers.insert(0, provide(org, name, generate(m)))
                elif callable(m):
                    param.providers.insert(0, provide(org, name, m))
        if isinstance(default, Provider):
            param.providers.insert(0, default)
        if isinstance(default, Depend):
            default.init_subscriber(providers)
            param.depend = default
        res.append(param)
    return res


R = TypeVar("R")
SUBSCRIBER: CtxItem["Subscriber"] = cast(CtxItem, "$subscriber")


@final
class Subscriber(Generic[R]):
    id: str
    callable_target: Callable[..., Awaitable[R]]
    priority: int
    providers: list[Provider | ProviderFactory]
    params: list[CompileParam]

    _callable_target: Callable[..., Any]
    _diffusions: list[Subscriber]

    def __init__(
        self,
        callable_target: TTarget[R],
        *,
        priority: int = 16,
        providers: Sequence[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
        dispose: Callable[[Self], None] | None = None,
        temporary: bool = False,
    ) -> None:
        self.id = str(uuid4())
        self.priority = priority
        self.auxiliaries = {}
        providers = providers or []
        self.providers = [p() if isinstance(p, type) else p for p in providers]
        self.providers.append(StateProvider())
        self._state = {}

        if hasattr(callable_target, "__providers__"):
            self.providers.extend(getattr(callable_target, "__providers__", []))
        self.params = _compile(callable_target, self.providers)
        self.callable_target = callable_target  # type: ignore
        self.is_cm = False
        if is_gen_callable(callable_target) or is_async_gen_callable(callable_target):
            if is_gen_callable(callable_target):
                self._callable_target = asynccontextmanager(run_sync_generator(callable_target))
            else:
                self._callable_target = asynccontextmanager(callable_target)  # type: ignore
            self.is_cm = True
        elif (wrapped := getattr(callable_target, "__wrapped__", None)) and (
            is_gen_callable(wrapped) or is_async_gen_callable(wrapped)
        ):
            if is_gen_callable(wrapped):
                self._callable_target = asynccontextmanager(run_sync_generator(wrapped))
            else:
                self._callable_target = asynccontextmanager(wrapped)  # type: ignore
            self.is_cm = True
        elif is_async(callable_target):
            self._callable_target = callable_target  # type: ignore
        else:
            self._callable_target = run_sync(callable_target)  # type: ignore

        self._dispose = dispose
        self._diffusions = []
        self.temporary = temporary

    def _recompile(self):
        self.params = _compile(self.callable_target, self.providers)

    async def __call__(self, *args, **kwargs) -> R:
        return await self.callable_target(*args, **kwargs)

    def __repr__(self):
        return f"Subscriber::{self.callable_target.__name__}"

    def __eq__(self, other):
        if isinstance(other, Subscriber):
            return other.id == self.id
        elif isinstance(other, str):
            return other == self.callable_target.__name__
        return False

    def dispose(self):
        if self._dispose:
            self._dispose(self)
        while self._diffusions:
            self._diffusions[0].dispose()

    async def handle(self, context: Contexts, inner=False) -> R:
        if not inner:
            context["$subscriber"] = self
        if self.is_cm and "$exit_stack" not in context:
            context["$exit_stack"] = AsyncExitStack()
        try:
            arguments: Contexts = {}  # type: ignore
            for param in self.params:
                if param.depend:
                    if not param.depend.cache:
                        arguments[param.name] = await param.depend.sub.handle(context.copy(), inner=True)  # type: ignore
                        continue
                    if "$depend_cache" not in context:
                        context["$depend_cache"] = {}
                    if param.depend.sub.callable_target in context["$depend_cache"]:
                        arguments[param.name] = context["$depend_cache"][param.depend.sub.callable_target]
                    else:
                        dep_res = await param.depend.sub.handle(context.copy(), inner=True)  # type: ignore
                        arguments[param.name] = dep_res
                        context["$depend_cache"][param.depend.sub.callable_target] = dep_res
                else:
                    arguments[param.name] = await param.solve(context)
            if self.is_cm:
                stack: AsyncExitStack = context["$exit_stack"]
                result = await stack.enter_async_context(self._callable_target(**arguments))
            else:
                result = await self._callable_target(**arguments)
            if self._diffusions:
                context["$result"] = result
                result = await self._run_diffuse(context)
        except InnerHandlerException as e:
            if inner:
                raise
            raise exception_handler(e.args[0], self.callable_target, context) from e  # type: ignore
        except Exception as e:
            raise exception_handler(e, self.callable_target, context, inner) from e  # type: ignore
        finally:
            if self.is_cm and "$exit_stack" in context:
                await context["$exit_stack"].aclose()
                context.pop("$exit_stack")
            _, exception, tb = sys.exc_info()
            if exception:
                context["$error"] = exception
        if self.temporary:
            self.dispose()
        return result

    async def _run_diffuse(self, context: Contexts) -> R:
        if len(self._diffusions) == 1:
            results = [await self._diffusions[0].handle(context.copy())]
        else:
            results = await asyncio.gather(*(sub.handle(context.copy()) for sub in self._diffusions), return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException):
                raise result
            if isinstance(result, Result):
                return result.value
            if result is not None and result is not False:
                return result
        return context["$result"]

    def diffuse(self, *, priority: int = 16, providers: list[Provider | ProviderFactory] | None = None):
        def wrapper(callable_target: TTarget[Any]):
            _providers = providers or []
            _providers.append(ResultProvider())
            _providers.extend(self.providers)
            sub = Subscriber(callable_target, priority=priority, providers=_providers, dispose=lambda x: self._diffusions.remove(x))
            self._diffusions.append(sub)
            return sub
        return wrapper
