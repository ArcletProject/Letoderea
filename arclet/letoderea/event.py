from __future__ import annotations

from typing import Any, Protocol, cast, runtime_checkable

from .typing import Contexts, CtxItem


@runtime_checkable
class BaseEvent(Protocol):
    async def gather(self, context: Contexts) -> Any: ...


EVENT: CtxItem[BaseEvent] = cast(CtxItem, "$event")


class ExceptionEvent:
    def __init__(self, origin: Any, exception: BaseException):
        self.exception = exception
        self.origin = origin

    async def gather(self, context: Contexts):
        context["exception"] = self.exception
        context["origin"] = self.origin

    __publisher__ = "$exception"
