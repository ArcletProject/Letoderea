from typing import TYPE_CHECKING

from tarina import ContextModel

if TYPE_CHECKING:
    from .core import EventSystem
    from .publisher import Publisher

system_ctx: ContextModel["EventSystem"] = ContextModel("system_ctx")
publisher_ctx: ContextModel["Publisher"] = ContextModel("publisher_ctx")
