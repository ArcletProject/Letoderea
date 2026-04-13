from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar, cast

T = TypeVar("T")


class CtxItem(Generic[T]):
    @classmethod
    def make(cls, name: str) -> "CtxItem[T]":
        return cast(CtxItem[T], cast(object, name))


class Contexts(dict[str, Any]):
    pass


EVENT = CtxItem[Any].make("$event")
shared_suppliers = []


async def generate_contexts(
    event: T, supplier:  Callable[[T, Contexts], Awaitable[Contexts | None]] | None = None, inherit_ctx: Contexts | None = None
) -> Contexts:
    contexts: Contexts = {EVENT: event, "$depend_cache": {}}  # type: ignore
    if supplier:
        await supplier(event, contexts)
    elif (_gather := getattr(event, "__context_gather__", getattr(event, "gather", None))) is not None:  # pragma: no cover
        await _gather(contexts)
    if shared_suppliers:
        for gather in shared_suppliers:
            await gather(contexts)
    if inherit_ctx:
        inherit_ctx.update(contexts)
        return inherit_ctx
    return contexts
