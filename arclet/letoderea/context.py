from typing import TYPE_CHECKING
from .typing import ContextModel
from .event import BaseEvent

if TYPE_CHECKING:
    from .core import EventSystem

event_ctx: ContextModel[BaseEvent] = ContextModel("event_ctx")
system_ctx: ContextModel['EventSystem'] = ContextModel("system_ctx")
