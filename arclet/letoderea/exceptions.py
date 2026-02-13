import functools
import inspect
import itertools
import pprint
import re
import sys
import traceback
from enum import Enum
from types import CodeType, TracebackType, FunctionType
from typing import Any, Final, cast

from .typing import Contexts


pat = re.compile(r"(async\s+)?def\s+(\w+)\s*(\[[\w.\[\], ]+\])?\s*\((?P<params>.*)\)")
pat1 = re.compile(r"(async\s+)?def\s+(\w+)\s*(\[[\w.\[\], ]+\])?\s*\(")
pat1_1 = re.compile(r"\)\s*(->\s*[\w.\[\], ]+)?\s*:")
pat2 = re.compile(r"lambda\s+(?P<params>.*):")


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


class Trace(traceback.TracebackException):
    def __init__(self, exc_type: type[BaseException], exc_value: BaseException, exc_traceback: TracebackType | None, **kwargs):  # pragma: no cover
        super().__init__(exc_type, exc_value, exc_traceback, **kwargs)
        self.exc_value = exc_value
        self.exc_traceback = exc_traceback


@functools.lru_cache(maxsize=None)
def get_caller_info(func: FunctionType, name: str | None = None) -> tuple[str, int, int, str, int, int]:  # pragma: no cover
    """Get the caller information of a function or method.

    Returns:
        - filename: The name of the file where the callable is defined.
        - lineno: The line number where the callable is defined.
        - offset: The character offset in the line where the parameter is defined.
        - line: The line of code where the callable is defined.
        - param_lineno: The line number where the parameter is defined.
        - param_offset: The character offset in the line where the parameter is defined.
    """
    code: CodeType = func.__code__
    lines = inspect.getsourcelines(func)
    lineno = code.co_firstlineno
    line = ""
    offset = 1
    if name is None:
        if code.co_name == "<lambda>":
            lineno += next(itertools.dropwhile(lambda x: not pat2.search(x[1]), enumerate(lines[0])))[0]
        else:
            lineno += next(itertools.dropwhile(lambda x: not pat1.search(x[1]), enumerate(lines[0])))[0]
        return code.co_filename, lineno, offset, line, lineno, offset
    param = str(inspect.signature(func).parameters[name])
    if code.co_name == "<lambda>":
        p = pat2
        def1 = next(itertools.dropwhile(lambda x: not pat2.search(x[1]), enumerate(lines[0])), None)
    else:
        p = pat
        def1 = next(itertools.dropwhile(lambda x: not pat.search(x[1]), enumerate(lines[0])), None)
    if def1 is not None:
        lineno += def1[0]
        line = def1[1]
        mat = p.search(line)
        assert mat
        params = mat.group("params").split(",")
        params_span = mat.span("params")
        target = next((slot for slot in params if name == slot.split(":")[0].strip() or name == slot.split("=")[0].strip()))
        offset += params_span[0] + line[params_span[0]:].index(target) + target.count(" ", 0, target.index(name))
    elif def2 := next(itertools.dropwhile(lambda x: not pat1.search(x[1]), enumerate(lines[0])), None):
        lineno += def2[0]
        for j, params in enumerate(lines[0][def2[0] + 1:]):
            target = next((slot for slot in params.split(",") if name == slot.split(":")[0].strip() or name == slot.split("=")[0].strip()), None)
            if target:
                lineno += j + 1
                offset += params.index(target) + target.count(" ", 0, target.index(name))
                line = params
                break
            if pat1_1.search(params):
                break
    return code.co_filename, lineno, offset, line, lineno, len(param) + offset


class ExceptionHandler:
    print_traceback = True

    @staticmethod
    def print_trace(te: Trace):  # pragma: no cover
        for line in te.format(chain=True):
            print(line, file=sys.stderr, end="")

    @staticmethod
    def call(e: Exception, callable_target: FunctionType, contexts: Contexts, inner: bool = False):
        if isinstance(e, UnresolvedRequirement) and not isinstance(e, SyntaxError):
            name, anno, _, pds = e.args
            param = f"{name}: {inspect.formatannotation(anno)}" if anno is not None else name
            etype: type[Exception] = type("UnresolvedRequirement", (UnresolvedRequirement, SyntaxError), {})  # type: ignore
            exc: SyntaxError = etype(
                f"Unable to parse parameter `{param}`"
                f"\n> providers on parameter `{param}`: "
                f"\n{pprint.pformat(pds, indent=2)}"
                f"\n> current context"
                f"\n{pprint.pformat(contexts)}",
                get_caller_info(callable_target, name),
            )
            exc.__origin_args__ = e.args
            exc.__traceback__ = e.__traceback__
            if inner:
                return InnerHandlerException(exc)
            if ExceptionHandler.print_traceback:  # pragma: no cover
                traceback.print_exception(etype, exc, e.__traceback__)
            return exc
        if inner:
            return InnerHandlerException(e)
        if isinstance(e, (ProviderUnsatisfied, _ExitException)):  # pragma: no cover
            return e
        if isinstance(e, InnerHandlerException):  # pragma: no cover
            _e = e.args[0]
            end_tb = tb = e.__traceback__
            while end_tb and end_tb.tb_next:
                if end_tb.tb_next.tb_next is None:
                    break
                end_tb = end_tb.tb_next
            end_tb.tb_next = e.args[0].__traceback__  # type: ignore
        else:
            _e = e
            tb = e.__traceback__
        if ExceptionHandler.print_traceback:  # pragma: no cover
            if isinstance(_e, UnresolvedRequirement):
                traceback.print_exception(SyntaxError, _e, tb)
            else:
                filename, lineno, *_ = get_caller_info(callable_target)
                summary = traceback.FrameSummary(filename, lineno, callable_target.__name__, locals={})
                te = Trace(_e.__class__, _e, tb, compact=True)
                te.stack.insert(0, summary)
                ExceptionHandler.print_trace(te)
        return _e


def switch_print_traceback(flag: bool):  # pragma: no cover
    ExceptionHandler.print_traceback = flag


STOP: Final = ExitState.stop
BLOCK: Final = ExitState.block
