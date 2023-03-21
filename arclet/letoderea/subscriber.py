from __future__ import annotations

from typing import Any, Callable, TypeVar, Generic

from .typing import TTarget
from .auxiliary import BaseAuxiliary
from .provider import Param, Provider
from .utils import argument_analysis, run_always_await


def _compile(
    target: Callable, providers: list[Provider]
) -> list[tuple[str, Any, Any, list[Provider]]]:
    res = []
    for name, anno, default in argument_analysis(target):
        catches = []
        for provider in providers:
            if provider.validate(Param(name, anno, default, bool(len(catches)))):
                catches.append(provider)
        if isinstance(default, Provider):
            catches.insert(0, default)
        res.append((name, anno, default, catches))
    return res


R = TypeVar("R")


class Subscriber(Generic[R]):
    name: str
    callable_target: TTarget[R]
    priority: int
    auxiliaries: list[BaseAuxiliary]
    providers: list[Provider]
    params: list[tuple[str, Any, Any, list[Provider]]]
    revise_mapping: dict[str, str]

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
        self.revise_mapping = {}

    async def __call__(self, *args, **kwargs) -> R:
        return await run_always_await(self.callable_target, *args, **kwargs)

    def __repr__(self):
        return f"Subscriber::{self.name}"

    def __eq__(self, other):
        if isinstance(other, Subscriber):
            return other.name == self.name
        elif isinstance(other, str):
            return other == self.name
