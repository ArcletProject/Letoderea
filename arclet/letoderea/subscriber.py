from __future__ import annotations

from uuid import uuid4
from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar
from collections.abc import Awaitable, Sequence
from typing_extensions import Self, get_args, get_origin
from typing import Annotated, final

from tarina import Empty, is_async, signatures

from .auxiliary import BaseAuxiliary, Scope
from .exceptions import UndefinedRequirement
from .provider import Param, Provider, ProviderFactory, provide
from .ref import Deref, generate
from .typing import Contexts, Force, TTarget, run_sync


@dataclass(init=False, eq=True)
class Depend:
    target: TTarget[Any]
    sub: Subscriber[Any]

    def __init__(self, callable_func: TTarget[Any]):
        self.target = callable_func

    def init_subscriber(self, provider: list[Provider | ProviderFactory]):
        self.sub = Subscriber(self.target, providers=provider)
        return self


def Depends(target: TTarget[Any]) -> Any:
    return Depend(target)


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
        if self.depend:
            return await self.depend.sub.handle(context)  # type: ignore
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


@final
class Subscriber(Generic[R]):
    id: str
    callable_target: Callable[..., Awaitable[R]]
    priority: int
    auxiliaries: dict[Scope, list[BaseAuxiliary]]
    providers: list[Provider | ProviderFactory]
    params: list[CompileParam]
    external_gather: Callable[[Any], Awaitable[Contexts]] | None = None

    def __init__(
        self,
        callable_target: TTarget[R],
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: Sequence[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
        dispose: Callable[[Self], None] | None = None,
    ) -> None:
        self.id = str(uuid4())
        self.priority = priority
        self.auxiliaries = {}
        providers = providers or []
        self.providers = [p() if isinstance(p, type) else p for p in providers]
        auxiliaries = auxiliaries or []
        if hasattr(callable_target, "__auxiliaries__"):
            auxiliaries.extend(getattr(callable_target, "__auxiliaries__", []))
        if hasattr(callable_target, "__providers__"):
            self.providers.extend(getattr(callable_target, "__providers__", []))
        for aux in auxiliaries:
            for scope in aux.scopes:
                self.auxiliaries.setdefault(scope, []).append(aux)
        for scope, value in self.auxiliaries.items():
            self.auxiliaries[scope] = sorted(value, key=lambda a: a.priority)  # type: ignore
        self.params = _compile(callable_target, self.providers)
        if is_async(callable_target):
            self.callable_target = callable_target  # type: ignore
        else:
            self.callable_target = run_sync(callable_target)  # type: ignore
        self.external_gather = None
        self._dispose = dispose

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

    async def handle(self, context: Contexts) -> R:
        arguments = {}
        for param in self.params:
            arguments[param.name] = await param.solve(context)
        return await self.callable_target(**arguments)
