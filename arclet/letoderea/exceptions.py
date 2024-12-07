import inspect
import pprint
import sys
import traceback
from typing import Callable

from .typing import Contexts


class UnexpectedArgument(Exception):
    pass


class UndefinedRequirement(Exception):
    pass


class JudgementError(Exception):
    pass


class PropagationCancelled(Exception):
    pass


class ParsingStop(Exception):
    pass


class InnerHandlerException(Exception):
    pass


def exception_handler(e: Exception, callable_target: Callable, contexts: Contexts, inner: bool = False):
    if isinstance(e, UndefinedRequirement) and not isinstance(e, SyntaxError):
        name, *_, pds = e.args
        param = inspect.signature(callable_target).parameters[name]
        code = callable_target.__code__  # type: ignore
        etype: type[Exception] = type(  # type: ignore
            "UndefinedRequirement",
            (
                UndefinedRequirement,
                SyntaxError,
            ),
            {},
        )
        _args = (code.co_filename, code.co_firstlineno, 1, str(param))
        if sys.version_info >= (3, 10):
            _args += (code.co_firstlineno, len(name) + 1)
        exc: SyntaxError = etype(
            f"Unable to parse parameter ({param})"
            f"\n--------------------------------------------------"
            f"\nproviders on parameter ({param}):"
            f"\n{pprint.pformat(pds)}"
            f"\n--------------------------------------------------"
            f"\ncurrent context"
            f"\n{pprint.pformat(contexts)}",
            _args,
        )
        exc.__traceback__ = e.__traceback__
        if inner:
            return InnerHandlerException(exc)
        traceback.print_exception(
            etype,
            exc,
            e.__traceback__,
        )
        return exc
    if isinstance(
        e,
        (
            ParsingStop,
            PropagationCancelled,
            JudgementError,
            UnexpectedArgument,
            InnerHandlerException,
        ),
    ):
        return InnerHandlerException(e) if inner else e
    if inner:
        return InnerHandlerException(e)
    traceback.print_exception(e.__class__, e, e.__traceback__)
    return e
