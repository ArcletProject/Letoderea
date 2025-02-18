from __future__ import annotations

import abc
from enum import Enum, auto
from collections import defaultdict
from collections.abc import Awaitable, Generator, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Final, Generic, TypeVar, cast, final, overload
from typing_extensions import Self, get_args, get_origin
from uuid import uuid4

from tarina import Empty, is_async, signatures

from .exceptions import (
    InnerHandlerException,
    ProviderUnsatisfied,
    UnresolvedRequirement,
    exception_handler,
)
from .provider import Param, Provider, ProviderFactory, provide
from .ref import Deref, generate
from .typing import (
    Contexts,
    CtxItem,
    Force,
    Result,
    TTarget,
    is_async_gen_callable,
    is_gen_callable,
    run_sync,
    run_sync_generator,
)


class ExitState(Enum):
    stop = auto()
    block = auto()


STOP: Final[ExitState] = ExitState.stop
BLOCK: Final[ExitState] = ExitState.block
RESULT: CtxItem["Any"] = cast(CtxItem, "$result")


class ResultProvider(Provider[Any]):
    def validate(self, param: Param):
        return param.name == "result"

    async def __call__(self, context: Contexts):
        return context.get(RESULT)


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


def depends(cache: bool = False) -> Callable[[TTarget[Any]], Any]:
    def wrapper(target: TTarget[Any]) -> Any:
        return Depend(target, cache)

    return wrapper


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
        raise UnresolvedRequirement(self.name, self.annotation, self.default, self.providers)


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


class Propagator(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def compose(self) -> Generator[TTarget | tuple[TTarget, bool] | tuple[TTarget, bool, int], None, None]: ...

    def __iter__(self):
        return self.compose()


@final
class Subscriber(Generic[R]):
    id: str
    callable_target: Callable[..., Awaitable[R]]
    priority: int
    providers: list[Provider | ProviderFactory]
    params: list[CompileParam]

    _callable_target: Callable[..., Any]

    def __init__(
        self,
        callable_target: TTarget[R],
        *,
        priority: int = 16,
        providers: Sequence[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
        dispose: Callable[[Self], None] | None = None,
        temporary: bool = False,
        skip_req_missing: bool = False,
    ) -> None:
        self.id = str(uuid4())
        self.priority = priority
        self.skip_req_missing = skip_req_missing
        self.auxiliaries = {}
        providers = providers or []
        self.providers = [p() if isinstance(p, type) else p for p in providers]
        self._propagates: list[Subscriber] = []
        self._cursor = 0

        if hasattr(callable_target, "__providers__"):
            self.providers.extend(getattr(callable_target, "__providers__", []))
        if hasattr(callable_target, "__propagates__"):
            for slot in getattr(callable_target, "__propagates__", []):
                self.propagates(*slot[0], prepend=slot[1])
        self.params = _compile(callable_target, self.providers)
        self.callable_target = callable_target  # type: ignore
        self.has_cm = False
        self.is_cm = False
        if is_gen_callable(callable_target) or is_async_gen_callable(callable_target):
            if is_gen_callable(callable_target):
                self._callable_target = asynccontextmanager(run_sync_generator(callable_target))
            else:
                self._callable_target = asynccontextmanager(callable_target)  # type: ignore
            self.has_cm = True
            self.is_cm = True
        elif (wrapped := getattr(callable_target, "__wrapped__", None)) and (
            is_gen_callable(wrapped) or is_async_gen_callable(wrapped)
        ):
            if is_gen_callable(wrapped):
                self._callable_target = asynccontextmanager(run_sync_generator(wrapped))
            else:
                self._callable_target = asynccontextmanager(wrapped)  # type: ignore
            self.has_cm = True
            self.is_cm = True
        elif is_async(callable_target):
            self._callable_target = callable_target  # type: ignore
        else:
            self._callable_target = run_sync(callable_target)  # type: ignore

        self._dispose = dispose
        self.temporary = temporary

    def _recompile(self):
        self.params = _compile(self.callable_target, self.providers)

    async def __call__(self, *args, **kwargs) -> R:
        return await self.callable_target(*args, **kwargs)

    def __repr__(self):
        lineno = self.callable_target.__code__.co_firstlineno
        return f"<Subscriber: {self.callable_target.__qualname__} at {self.callable_target.__module__}:{lineno}>"

    def __eq__(self, other):
        if isinstance(other, Subscriber):
            return other.id == self.id
        elif isinstance(other, str):
            return other == self.callable_target.__name__
        return False

    def dispose(self):
        if self._dispose:
            self._dispose(self)
        self._dispose = None
        while self._propagates:
            self._propagates[0].dispose()

    async def handle(self, context: Contexts, inner=False) -> R | ExitState:
        if not inner:
            context["$subscriber"] = self
            if self.has_cm and "$exit_stack" not in context:
                context["$exit_stack"] = AsyncExitStack()
        try:
            if self._cursor:
                _res = await self._run_propagate(context, self._propagates[: self._cursor])
                if _res is STOP or _res is BLOCK:
                    return _res
            arguments: Contexts = {}  # type: ignore
            for param in self.params:
                if param.depend:
                    if not param.depend.cache:
                        dep_res = await param.depend.sub.handle(context.copy(), inner=True)  # type: ignore
                        if dep_res is STOP or dep_res is BLOCK:
                            return dep_res
                        arguments[param.name] = dep_res
                        continue
                    if "$depend_cache" not in context:
                        context["$depend_cache"] = {}
                    if param.depend.sub.callable_target in context["$depend_cache"]:
                        arguments[param.name] = context["$depend_cache"][param.depend.sub.callable_target]
                    else:
                        dep_res = await param.depend.sub.handle(context.copy(), inner=True)  # type: ignore
                        if dep_res is STOP or dep_res is BLOCK:
                            return dep_res
                        arguments[param.name] = dep_res
                        context["$depend_cache"][param.depend.sub.callable_target] = dep_res
                else:
                    arguments[param.name] = await param.solve(context)
            if self.is_cm:
                stack: AsyncExitStack = context["$exit_stack"]
                result = await stack.enter_async_context(self._callable_target(**arguments))
            else:
                result = await self._callable_target(**arguments)
            if self._propagates:
                context["$result"] = result
                result = (await self._run_propagate(context, self._propagates[self._cursor :])) or result
                if result is STOP or result is BLOCK:
                    return result
        except InnerHandlerException as e:
            if inner:
                raise
            e1 = e.args[0]
            if isinstance(e1, (UnresolvedRequirement, ProviderUnsatisfied)) and self.skip_req_missing:
                return STOP
            raise exception_handler(e1, self.callable_target, context, inner) from e  # type: ignore
        except Exception as e:
            if isinstance(e, (UnresolvedRequirement, ProviderUnsatisfied)) and self.skip_req_missing:
                return STOP
            raise exception_handler(e, self.callable_target, context, inner) from e  # type: ignore
        finally:
            if not inner:
                if self.has_cm and "$exit_stack" in context:
                    await context["$exit_stack"].aclose()
                    context.pop("$exit_stack")
                context.clear()
            if self.temporary:
                self.dispose()
        return result

    async def _run_propagate(self, context: Contexts, propagates: list[Subscriber]):
        queue = sorted(propagates, key=lambda x: x.priority).copy()
        pending: defaultdict[str, list[Subscriber]] = defaultdict(list)
        while queue:
            sub = queue.pop(0)
            try:
                result = await sub.handle(context, inner=True)
            except InnerHandlerException as e:
                exc = e.args[0]
                if isinstance(exc, UnresolvedRequirement):
                    pending[exc.__origin_args__[0]].append(sub)
                elif isinstance(exc, ProviderUnsatisfied):
                    pending[exc.source_key].append(sub)
                else:
                    raise
            else:
                if result is STOP or result is BLOCK:
                    return result
                if isinstance(result, dict):
                    context.update(result)
                elif isinstance(result, Result):
                    context["$result"] = result.value
                elif result is not None:
                    context["$result"] = result
                if pending:
                    for key in list(pending.keys()):
                        if key not in context:
                            continue
                        await self._run_propagate(context, pending.pop(key))
        if pending:
            key, (sub, *_) = pending.popitem()
            param = next(p for p in sub.params if p.name == key)
            raise exception_handler(
                UnresolvedRequirement(param.name, param.annotation, param.default, param.providers),
                sub.callable_target,
                context,
                inner=True,
            )
        return context.get(RESULT)

    @overload
    def propagate(
        self,
        func: TTarget[Any],
        *,
        prepend: bool = False,
        priority: int = 16,
        providers: list[Provider | ProviderFactory] | None = None,
        temporary: bool = False,
    ) -> Callable[[], None]: ...

    @overload
    def propagate(
        self,
        func: Propagator,
        *,
        providers: list[Provider | ProviderFactory] | None = None,
        temporary: bool = False,
    ) -> Callable[[], None]: ...

    @overload
    def propagate(
        self,
        *,
        prepend: bool = False,
        priority: int = 16,
        providers: list[Provider | ProviderFactory] | None = None,
        temporary: bool = False,
    ) -> Callable[[TTarget[Any]], Callable[[], None]]: ...

    def propagate(
        self,
        func: TTarget[Any] | Propagator | None = None,
        *,
        prepend: bool = False,
        priority: int = 16,
        providers: list[Provider | ProviderFactory] | None = None,
        temporary: bool = False,
    ):
        if isinstance(func, Propagator):
            disposes = []
            for slot in func.compose():
                disposes.append(
                    self.propagate(slot[0], prepend=slot[1], priority=slot[2] if len(slot) == 3 else 16)
                    if isinstance(slot, tuple)
                    else self.propagate(slot, priority=16)
                )

            def _():
                for dispose in disposes:
                    dispose()
            return _

        def wrapper(callable_target: TTarget[Any], /):
            _providers = providers or []
            _providers.extend(self.providers)
            if prepend:

                def _dispose(x: Subscriber):
                    self._propagates.remove(x)
                    self._cursor -= 1

                if isinstance(callable_target, Subscriber):
                    sub = callable_target
                    origin_dispose = sub._dispose
                    sub._dispose = lambda x: (origin_dispose(x), _dispose(x))  # type: ignore
                    sub.temporary = temporary
                else:
                    sub = Subscriber(
                        callable_target,
                        priority=priority,
                        providers=_providers,
                        dispose=_dispose,
                        temporary=temporary,
                    )
                self._propagates.insert(self._cursor, sub)
                self._cursor += 1
            else:
                if isinstance(callable_target, Subscriber):
                    sub = callable_target
                    sub.temporary = temporary
                    sub.providers.append(ResultProvider())
                    sub._recompile()
                    origin_dispose = sub._dispose
                    sub._dispose = lambda x: (origin_dispose(x), self._propagates.remove(x))  # type: ignore
                else:
                    _providers.append(ResultProvider())
                    sub = Subscriber(
                        callable_target,
                        priority=priority,
                        providers=_providers,
                        dispose=lambda x: self._propagates.remove(x),
                        temporary=temporary,
                    )
                self._propagates.append(sub)
            if sub.has_cm:
                self.has_cm = True
            return sub.dispose

        if func:
            return wrapper(func)
        return wrapper

    def propagates(self, *funcs: TTarget[Any] | Propagator, prepend: bool = False):
        for func in funcs:
            self.propagate(func, prepend=prepend)  # type: ignore

        return self

    def get_propagator(self, func: TTarget[R]) -> Subscriber[R]:
        for sub in self._propagates:
            if sub.callable_target == func:
                return sub
            if hasattr(sub.callable_target, "__func__") and sub.callable_target.__func__ == func:  # type: ignore
                return sub
        raise ValueError(f"Propagator {func} not found")


def defer(ctx: Contexts | TTarget, func: Callable[..., Any]):
    if isinstance(ctx, dict):
        sub = ctx[SUBSCRIBER]
    elif isinstance(ctx, Subscriber):
        sub = ctx
    else:
        raise TypeError(f"Unsupported type {type(ctx)}")
    return sub.propagate(func, temporary=True)
