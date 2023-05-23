from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Generic, TypeVar
from tarina import signatures, run_always_await
from typing_extensions import Annotated, get_origin, get_args

from .auxiliary import Scope, AuxType, BaseAuxiliary, Executor, combine
from .provider import Param, Provider, provide
from .typing import TTarget
from .ref import Deref, generate


@dataclass
class CompileParam:
    name: str
    annotation: Any
    default: Any
    providers: list[Provider]
    depend: Provider | None

    __slots__ = ("name", "annotation", "default", "providers", "depend")


def _compile(target: Callable, providers: list[Provider]) -> list[CompileParam]:
    res = []
    for name, anno, default in signatures(target):
        param = CompileParam(name, anno, default, [], None)
        for _provider in providers:
            if _provider.validate(
                Param(name, anno, default, bool(len(param.providers)))
            ):
                param.providers.append(_provider)
        if get_origin(anno) is Annotated:
            org, *meta = get_args(anno)
            for m in reversed(meta):
                if isinstance(m, Provider):
                    param.providers.insert(0, m)
                elif isinstance(m, str):
                    param.providers.insert(0, provide(org, name, lambda x: x.get(m))())
                elif isinstance(m, Deref):
                    param.providers.insert(0, provide(org, name, generate(m))())
                elif callable(m):
                    param.providers.insert(0, provide(org, name, m)())
        if isinstance(default, Provider):
            param.providers.insert(0, default)
        if isinstance(default, BaseAuxiliary) and (default.type == AuxType.depend):
            param.depend = provide(anno, call=partial(default, "parsing"))()
        res.append(param)
    return res


R = TypeVar("R")


class Subscriber(Generic[R]):
    name: str
    callable_target: TTarget[R]
    priority: int
    auxiliaries: dict[Scope, list[Executor]]
    providers: list[Provider]
    params: list[CompileParam]

    def __init__(
        self,
        callable_target: TTarget[R],
        *,
        priority: int = 16,
        name: str | None = None,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider]] | None = None,
    ) -> None:
        self.callable_target = callable_target
        self.name = name or callable_target.__name__
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
            self.auxiliaries[scope] = combine(value)  # type: ignore
        self.params = _compile(callable_target, self.providers)

    async def __call__(self, *args, **kwargs) -> R:
        return await run_always_await(self.callable_target, *args, **kwargs)

    def __repr__(self):
        return f"Subscriber::{self.name}"

    def __eq__(self, other):
        if isinstance(other, Subscriber):
            return other.name == self.name
        elif isinstance(other, str):
            return other == self.name
