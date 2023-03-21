from __future__ import annotations

from functools import partial
from dataclasses import dataclass
from typing import Any, Callable, TypeVar, Generic

from .typing import TTarget
from .auxiliary import BaseAuxiliary, AuxType, Scope
from .provider import Param, Provider, provider
from .utils import argument_analysis, run_always_await


@dataclass
class CompileParam:
    name: str
    annotation: Any
    default: Any
    providers: list[Provider]
    depend: Provider | None

    __slots__ = ("name", "annotation", "default", "providers", "depend")


def _compile(
    target: Callable, providers: list[Provider]
) -> list[CompileParam]:
    res = []
    for name, anno, default in argument_analysis(target):
        param = CompileParam(name, anno, default, [], None)
        for _provider in providers:
            if _provider.validate(Param(name, anno, default, bool(len(param.providers)))):
                param.providers.append(_provider)
        if isinstance(default, Provider):
            param.providers.insert(0, default)
        if isinstance(default, BaseAuxiliary) and (aux := default.handlers.get(Scope.parsing)):
            if depend := next(filter(lambda x: x.aux_type == AuxType.supply, aux), None):
                param.depend = provider(anno, call=partial(depend.supply, default))()
        res.append(param)
    return res


R = TypeVar("R")


class Subscriber(Generic[R]):
    name: str
    callable_target: TTarget[R]
    priority: int
    auxiliaries: list[BaseAuxiliary]
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
        self.auxiliaries = auxiliaries or []
        providers = providers or []
        self.providers = [p() if isinstance(p, type) else p for p in providers]
        if hasattr(callable_target, "__auxiliaries__"):
            self.auxiliaries.extend(getattr(callable_target, "__auxiliaries__", []))
        if hasattr(callable_target, "__providers__"):
            self.providers.extend(getattr(callable_target, "__providers__", []))
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
