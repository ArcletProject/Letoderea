from typing import TYPE_CHECKING

from .typing import ContextModel

if TYPE_CHECKING:
    from .core import EventSystem

system_ctx: ContextModel["EventSystem"] = ContextModel("system_ctx")
