import inspect
import pprint
import sys
import traceback
from enum import Enum
from types import CodeType
from typing import Any, Callable, Final, cast

from .typing import Contexts


class UnresolvedRequirement(Exception):
    __origin_args__: tuple[str, Any, Any, list[Any]]


class ProviderUnsatisfied(Exception):
    def __init__(self, source_key: str):
        self.source_key = source_key


class _ExitException(Exception):
    pass


class ExitState(_ExitException, Enum):
    stop = _ExitException("Handle stopped")
    block = _ExitException("Propagation blocked")

    def finish(self, value):
        return cast(ExitState, _ExitException(value, self is self.block))

    def __str__(self):
        return super(Exception, self).__str__()


class InnerHandlerException(Exception):
    pass


class ExceptionHandler:
    print_traceback = True

    @staticmethod
    def call(e: Exception, callable_target: Callable, contexts: Contexts, inner: bool = False):
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
            if sys.version_info >= (3, 10):  # pragma: no cover
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
            if ExceptionHandler.print_traceback:  # pragma: no cover
                traceback.print_exception(
                    etype,
                    exc,
                    e.__traceback__,
                )
            return exc
        if inner:
            return InnerHandlerException(e)
        if isinstance(e, (InnerHandlerException, ProviderUnsatisfied, _ExitException)):
            return e
        if ExceptionHandler.print_traceback:  # pragma: no cover
            traceback.print_exception(e.__class__, e, e.__traceback__)
        return e


def switch_print_traceback(flag: bool):  # pragma: no cover
    ExceptionHandler.print_traceback = flag


STOP: Final = ExitState.stop
BLOCK: Final = ExitState.block
