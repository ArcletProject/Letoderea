from __future__ import annotations

import asyncio
import atexit
import inspect
from collections.abc import Awaitable, Callable, Hashable, Iterable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeAlias, overload
from typing_extensions import TypeVar
from weakref import WeakKeyDictionary

from tarina import is_async

T = TypeVar("T")
T_Weak = TypeVar("T_Weak", bound=Hashable | Callable)

TTarget: TypeAlias = Callable[..., Awaitable[T]] | Callable[..., T]
TCallable = TypeVar("TCallable", bound=Callable[..., Any])


@dataclass(slots=True, frozen=True)
class Force:
    """用于转义在本框架中特殊部分的特殊值"""

    value: Any


@dataclass(slots=True, frozen=True)
class Result(Generic[T]):
    """用于标记一个事件响应器的处理结果，通常应用在某个事件响应器的处理结果需要被事件发布者使用的情况"""
    value: T


class Resultable(Protocol[T]):
    def check_result(self, value: Any) -> Result[T] | None: ...


async def run_always_await(target: Callable[..., Any] | Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
    obj = target(*args, **kwargs)
    if is_async(target) or inspect.isawaitable(obj):
        obj = await obj  # type: ignore
    return obj


def _delete(mapping, key):
    if key in mapping:
        del mapping[key]
        return True
    return False


class DisposableList(Generic[T_Weak]):
    def __init__(self, iterable: Iterable[T_Weak] | None = None):
        self.sn = 0
        self.data: dict[int, T_Weak] = {}
        self.ref: WeakKeyDictionary[T_Weak, int] = WeakKeyDictionary()
        if iterable is not None:
            for item in iterable:
                self.append(item)

    def __len__(self):
        return self.data.__len__()

    def append(self, item: T_Weak):
        sn = self.sn
        self.data[sn] = item
        self.ref[item] = sn
        self.sn += 1
        return lambda: _delete(self.data, sn)

    def insert(self, index, value):  # pragma: no cover
        raise NotImplementedError("DisposableList does not support insert")

    def remove(self, item: T_Weak):
        sn = self.ref.get(item)
        if sn is None:
            return False
        return _delete(self.data, sn)  # pragma: no cover

    def clear(self):
        values = list(self.data.values())
        self.data.clear()
        return reversed(values)

    def __iter__(self):
        return iter(self.data.values())

    @overload
    def __getitem__(self, index: int) -> T_Weak: ...

    @overload
    def __getitem__(self, index: slice[int | None]) -> "DisposableList[T_Weak]": ...

    def __getitem__(self, index):  # pragma: no cover
        if isinstance(index, int):
            return self.data[index]
        elif isinstance(index, slice):
            return DisposableList([self.data[i] for i in range(*index.indices(self.sn))])
        else:
            raise TypeError(f"Invalid index type: {type(index)}")

    @overload
    def __setitem__(self, index: int, value: T_Weak) -> Callable[[], bool]: ...

    @overload
    def __setitem__(self, index: slice[int | None], value: Iterable[T_Weak]) -> Callable[[], list[bool]]: ...

    def __setitem__(self, index, value):  # pragma: no cover
        if isinstance(index, int):
            self.data[index] = value
            self.ref[value] = index
            return lambda: _delete(self.data, index)
        if isinstance(index, slice):
            indices = range(*index.indices(self.sn))
            for i, v in zip(indices, value):
                self.data[i] = v
                self.ref[v] = i
            return lambda: [_delete(self.data, i) for i in indices]
        raise TypeError(f"Invalid index type: {type(index)}")

    @overload
    def __delitem__(self, index: int) -> bool: ...

    @overload
    def __delitem__(self, index: slice[int | None]) -> list[bool]: ...

    def __delitem__(self, index):  # pragma: no cover
        if isinstance(index, int):
            return _delete(self.data, index)
        if isinstance(index, slice):
            return [
                _delete(self.data, i) for i in range(*index.indices(self.sn))
            ]
        raise TypeError(f"Invalid index type: {type(index)}")


class _EventSystem:
    ref_tasks: set[asyncio.Task] = set()
    loop: asyncio.AbstractEventLoop | None = None


def add_task(coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
    loop = _EventSystem.loop or asyncio.get_running_loop()
    task = loop.create_task(coro)
    _EventSystem.ref_tasks.add(task)
    task.add_done_callback(_EventSystem.ref_tasks.discard)
    return task


def set_event_loop(loop: asyncio.AbstractEventLoop):  # pragma: no cover
    _EventSystem.loop = loop


@atexit.register
def _cleanup():  # pragma: no cover
    for task in _EventSystem.ref_tasks:
        if not task.done() and not task.get_loop().is_closed():
            task.cancel()
    _EventSystem.ref_tasks.clear()
