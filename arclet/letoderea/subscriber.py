from __future__ import annotations

from inspect import isclass
from typing import Any, Callable

from .auxiliary import BaseAuxiliary
from .provider import ProvideMode, Provider
from .utils import argument_analysis


def bind(
    target: Callable, providers: list[Provider]
) -> dict[str, tuple[Any, Any, list[Provider]]]:
    res = {}
    provide_map = {}
    generic_map = {}
    wildcard_providers = []
    for provider in providers:
        if provider.mode == ProvideMode.wildcard:
            wildcard_providers.append(provider)
        elif provider.mode == ProvideMode.subclass:
            for t in provider.origin.mro()[:-1]:
                provide_map.setdefault(t, []).append(provider)
        elif provider.mode == ProvideMode.generic:
            generic_map.setdefault(provider.origin, []).append(provider)
        else:
            provide_map.setdefault(provider.origin, []).append(provider)

    for name, annotation, default in argument_analysis(target):
        if annotation in provide_map:
            res[name] = (
                annotation,
                default,
                sorted(provide_map[annotation], key=lambda x: x.name == name, reverse=True)
            )
        else:
            res[name] = next(
                (
                    (annotation, default, sorted(providers, key=lambda x: x.name == name, reverse=True))
                    for t, providers in generic_map.items()
                    if issubclass(annotation, t)
                ),
                (annotation, default, wildcard_providers),
            )
        if isinstance(default, Provider):
            res[name][2].insert(0, default)
    return res


class Subscriber:
    name: str
    callable_target: Callable
    priority: int
    auxiliaries: list[BaseAuxiliary]
    providers: list[Provider]
    params: dict[str, tuple[Any, Any, list[Provider]]]
    revise_mapping: dict[str, str]

    def __init__(
        self,
        callable_target: Callable,
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
        self.providers = providers or []
        for index, provider in enumerate(self.providers):
            if isclass(provider):
                provider: type[Provider]
                self.providers[index] = provider()
        if hasattr(callable_target, "__auxiliaries__"):
            self.auxiliaries.extend(getattr(callable_target, "__auxiliaries__", []))
        if hasattr(callable_target, "__providers__"):
            self.providers.extend(getattr(callable_target, "__providers__", []))
        self.params = bind(callable_target, self.providers)
        self.revise_mapping = {}

    def __call__(self, *args, **kwargs):
        return self.callable_target(*args, **kwargs)

    def __repr__(self):
        return f"Subscriber::{self.name}"

    def __eq__(self, other):
        if isinstance(other, Subscriber):
            return other.name == self.name
        elif isinstance(other, str):
            return other == self.name
