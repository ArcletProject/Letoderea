import asyncio

from collections.abc import Awaitable, Callable, Iterable, AsyncIterable
from dataclasses import dataclass
from typing import TypeAlias, Protocol, Generic, Any, overload
from typing_extensions import TypeVar
from weakref import WeakKeyDictionary

from tarina import is_awaitable, is_async

T = TypeVar("T")
_Awaitable: TypeAlias = T | Awaitable[T]
TA = TypeVar("TA", bound=_Awaitable[None], default=_Awaitable[None], covariant=True)
Disposable: TypeAlias = Callable[[], T]


class AsyncDisposable(Awaitable[Callable[[], TA]], Protocol[TA]):
    def __call__(self) -> TA: ...


SyncEffect: TypeAlias = Disposable[T] | Iterable[Disposable[T]]
AsyncEffect: TypeAlias = Awaitable[Disposable[T]] | AsyncIterable[Disposable[T]]
Effect: TypeAlias = SyncEffect[T] | AsyncEffect[T]


@dataclass(slots=True)
class _Meta:
    label: str
    children: list["_Meta"]


@dataclass(slots=True)
class _Runner(Generic[T]):
    epoch: T
    execute: Callable[[], Any]
    collect: Callable[[Disposable], None]


def _delete(mapping, key):
    if key in mapping:
        del mapping[key]
        return True
    return False


class DisposableList(Generic[T]):
    def __init__(self):
        self.sn = 0
        self.data: dict[int, T] = {}
        self.ref: WeakKeyDictionary[T, int] = WeakKeyDictionary()

    def __len__(self):
        return self.data.__len__()

    def append(self, item: T):
        sn = self.sn
        self.data[sn] = item
        self.ref[item] = sn
        self.sn += 1
        return lambda: _delete(self.data, sn)

    def remove(self, item: T):
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


class EffectManager:
    def __init__(self):
        self._disposables: DisposableList[Disposable] = DisposableList()

    def _execute(self, runner: _Runner[T]):
        old_epoch = runner.epoch

        def _safe_collect(dispose: Disposable | None):
            if callable(dispose):
                runner.collect(dispose)
            elif dispose is not None:  # pragma: no cover
                raise TypeError(f"Effect collect expected a Disposable, got {type(dispose)}")

        effect: Effect[T] = runner.execute()
        if not effect:  # pragma: no cover
            return
        if isinstance(effect, Iterable):
            for dispose in effect:
                _safe_collect(dispose)
            return
        if isinstance(effect, AsyncIterable):
            iter_ = aiter(effect)

            async def _collect_async():
                await asyncio.sleep(0)
                while runner.epoch == old_epoch:
                    try:
                        _safe_collect(await anext(iter_))
                    except StopAsyncIteration:
                        break
            return _collect_async()
        if is_awaitable(effect):
            async def _collect_async():
                d = await effect
                _safe_collect(d)
            return _collect_async()
        if callable(effect):
            runner.collect(effect)
            return
        raise TypeError(f"Effect execute expected a Disposable or an Effect, got {type(effect)}")  # pragma: no cover

    def _collect_disposable(
        self,
        dispose: Disposable,
        disposables: list[Disposable],
        meta: _Meta,
    ) -> None:
        """收集清理函数"""
        disposables.append(dispose)
        self._disposables.remove(dispose)

        child_meta = getattr(dispose, "__effect__", None)
        if child_meta:
            meta.children.append(child_meta)

    @overload
    def effect(self, execute: Callable[[], SyncEffect[Awaitable[None]]], label: str = "") -> Disposable[Awaitable[None]]:
        ...

    @overload
    def effect(self, execute: Callable[[], SyncEffect], label: str = "") -> Disposable[None]:
        ...

    @overload
    def effect(self, execute: Callable[[], AsyncEffect], label: str = "") -> AsyncDisposable[Awaitable[None]]:
        ...

    def effect(self, execute: Callable[[], Effect], label: str = ""):  # type: ignore
        disposables: list[Disposable] = []

        async def dispose():
            for dispose_fn in disposables[:][::-1]:
                result = dispose_fn()
                while result is not None and is_awaitable(result):
                    result = await result
            disposables.clear()

        meta = _Meta(label, [])
        runner = _Runner(True, execute, lambda d: self._collect_disposable(d, disposables, meta))

        task_: asyncio.Future[None] | Awaitable[None] | None = None
        try:
            task_ = self._execute(runner)
        except Exception:  # pragma: no cover
            asyncio.get_event_loop().call_soon(lambda: asyncio.create_task(dispose()))
            raise

        async def dispose_async():  # pragma: no cover
            if not runner.epoch:
                return
            runner.epoch = False
            await dispose()

        if task_ is not None:
            async def guarded_task():
                try:
                    await task_
                except Exception:  # pragma: no cover
                    await dispose_async()
                    raise

            task = asyncio.create_task(guarded_task())

            async def wrapper_with_task():
                if not runner.epoch:  # pragma: no cover
                    return
                runner.epoch = False
                try:
                    await task
                finally:
                    await dispose()

            wrapper = wrapper_with_task  # type: ignore
        else:
            if all(not is_async(d) for d in disposables):
                def wrapper():
                    if not runner.epoch:  # pragma: no cover
                        return
                    runner.epoch = False
                    for dispose_fn in disposables[:][::-1]:
                        dispose_fn()
                    disposables.clear()
                    return
            else:
                async def wrapper_with_task():
                    if not runner.epoch:  # pragma: no cover
                        return
                    runner.epoch = False
                    await dispose()

                wrapper = wrapper_with_task  # type: ignore
        wrapper.__effect__ = meta
        disposables.append(self._disposables.append(wrapper))
        return wrapper  # type: ignore

    def get_effects(self):
        metas = [getattr(d, "__effect__", None) for d in self._disposables]
        return [m for m in metas if m is not None]

    def dispose(self):
        tasks: set[asyncio.Task] = set()
        for d in self._disposables.clear():
            r = d()
            if r is not None and is_awaitable(r):  # pragma: no cover
                tasks.add(asyncio.create_task(r))  # type: ignore
        return tasks

    async def cleanup(self):
        async def wrapper(dispose: Disposable):
            try:
                r = dispose()
                while r is not None and is_awaitable(r):
                    r = await r
            except Exception as e:  # pragma: no cover
                print("Error during effect cleanup", repr(e))

        tasks = [wrapper(d) for d in self._disposables.clear()]
        await asyncio.gather(*tasks, return_exceptions=True)

    @property
    def size(self):
        return len(self._disposables)
