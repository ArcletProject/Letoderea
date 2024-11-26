from typing import TYPE_CHECKING

from tarina import ContextModel

if TYPE_CHECKING:
    from .publisher import Publisher

publisher_ctx: ContextModel["Publisher"] = ContextModel("publisher_ctx")
