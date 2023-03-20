from __future__ import annotations

from typing import Any, Callable, TypeVar, Generic

from .typing import TTarget
from .auxiliary import BaseAuxiliary
from .provider import ProvideMode, Provider
from .utils import argument_analysis, run_always_await


def _compile(
    target: Callable, providers: list[Provider]
) -> list[tuple[str, Any, Any, list[Provider]]]:
    res: dict[str, tuple[Any, Any, list[Provider]]] = {}

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
        if providers := provide_map.get(annotation, []):
            res[name] = (
                annotation,
                default,
                sorted(
                    filter(
                        lambda x: True if x.target == "$" else x.target == name,
                        providers,
                    ),
                    key=lambda x: x.target == target,
                    reverse=True,
                ),
            )
        else:
            for t, providers in generic_map.items():
                if annotation and issubclass(annotation, t):
                    res[name] = (
                        annotation,
                        default,
                        sorted(
                            filter(
                                lambda x: True if x.target == "$" else x.target == name,
                                providers,
                            ),
                            key=lambda x: x.target == target,
                            reverse=True,
                        ),
                    )
                    break
        if name not in res:
            name_spec = [wild for wild in wildcard_providers if wild.target == name]
            res[name] = (
                annotation,
                default,
                name_spec or ([] if annotation else wildcard_providers),
            )
        if isinstance(default, Provider):
            res[name][2].insert(0, default)
    return [(k, v[0], v[1], v[2]) for k, v in res.items()]


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
