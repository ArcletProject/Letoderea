import inspect
import pprint
import sys
import traceback
from types import CodeType
from typing import Any, Callable

from .typing import Contexts


class UnresolvedRequirement(Exception):
    __origin_args__: tuple[str, Any, Any, list[Any]]


class ProviderUnsatisfied(Exception):
    def __init__(self, source_key: str):
        self.source_key = source_key


class InnerHandlerException(Exception):
    pass


def exception_handler(e: Exception, callable_target: Callable, contexts: Contexts, inner: bool = False):
    if isinstance(e, UnresolvedRequirement) and not isinstance(e, SyntaxError):
        name, *_, pds = e.args
        param = inspect.signature(callable_target).parameters[name]
        code: CodeType = callable_target.__code__  # type: ignore
        etype: type[Exception] = type(  # type: ignore
            "UnresolvedRequirement",
            (
                UnresolvedRequirement,
                SyntaxError,
            ),
            {},
        )
        _args = (code.co_filename, code.co_firstlineno, 1, str(param))
        if sys.version_info >= (3, 10):
            _args += (code.co_firstlineno, len(name) + 1)
        exc: SyntaxError = etype(
            f"Unable to parse parameter `{param}`"
            f"\n> providers on parameter `{param}`: "
            f"\n{pprint.pformat(pds, indent=2)}"
            f"\n> current context"
            f"\n{pprint.pformat(contexts)}",
            _args,
        )
        exc.__origin_args__ = e.args
        exc.__traceback__ = e.__traceback__
        if inner:
            return InnerHandlerException(exc)
        traceback.print_exception(
            etype,
            exc,
            e.__traceback__,
        )
        return exc
    if inner:
        return InnerHandlerException(e)
    if isinstance(e, (InnerHandlerException, ProviderUnsatisfied)):
        return e
    traceback.print_exception(e.__class__, e, e.__traceback__)
    return e
