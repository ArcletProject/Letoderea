from typing import TYPE_CHECKING

from tarina import ContextModel

if TYPE_CHECKING:
    from .scope import Scope

scope_ctx: ContextModel["Scope"] = ContextModel("scope_ctx")
