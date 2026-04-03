from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast, overload
from typing_extensions import Self

T = TypeVar("T")
T1 = TypeVar("T1")


class CtxItem(Generic[T]):
    @classmethod
    def make(cls, name: str) -> CtxItem[T]:
        return cast(CtxItem[T], cast(object, name))


class Contexts(dict[str, Any]):
    if TYPE_CHECKING:

        def copy(self) -> Self: ...

        @overload
        def __getitem__(self, item: CtxItem[T1]) -> T1: ...

        @overload
        def __getitem__(self, item: str) -> Any: ...

        def __getitem__(self, item: str | CtxItem[T1]) -> Any: ...

        @overload
        def __setitem__(self, key: CtxItem[T1], value: T1, /) -> None: ...

        @overload
        def __setitem__(self, key: str, value: Any, /) -> None: ...

        def __setitem__(self, key: str | CtxItem[T1], value: Any, /): ...

        @overload
        def get(self, __key: CtxItem[T1]) -> T1 | None: ...

        @overload
        def get(self, __key: str) -> Any | None: ...

        @overload
        def get(self, __key: CtxItem[T1], __default: T1) -> T1: ...

        @overload
        def get(self, __key: str, __default: Any) -> Any: ...

        @overload
        def get(self, __key: CtxItem[T1], __default: T) -> T1 | T: ...

        def get(self, __key: str | CtxItem[T1], __default: Any = ...) -> Any: ...  # type: ignore

    ...


EVENT: CtxItem[Any] = CtxItem.make("$event")
shared_suppliers: list[Callable[[Contexts], Awaitable[None]]] = []


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
