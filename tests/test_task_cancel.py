import asyncio

import pytest

import arclet.letoderea as le
from arclet.letoderea import ExitState, Subscriber


@le.make_event(name="cancel")
class CancelEvent:
    foo: str


@pytest.mark.asyncio
async def test_cancel_running():
    sub = Subscriber(lambda: None)

    async def coro():
        try:
            await asyncio.sleep(10)
        finally:
            pass

    task = asyncio.create_task(coro())
    sub._tasks.add(task)
    assert sub.running == frozenset({task})

    cancelled = sub.cancel_running()
    assert cancelled == {task}
    assert sub.running == frozenset()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_dispose_returns_cancelled_tasks():
    sub = Subscriber(lambda: None)

    async def coro():
        await asyncio.sleep(10)

    task = asyncio.create_task(coro())
    sub._tasks.add(task)

    result = sub.dispose()
    assert result == {task}
    assert sub.running == frozenset()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_dispose_aggregates_attach_disposes():
    sub = Subscriber(lambda: None)

    async def coro():
        await asyncio.sleep(0.01)

    task = asyncio.create_task(coro())

    def _dispose(_sub):
        return {task}

    sub._attach_disposes(_dispose)
    result = sub.dispose()
    assert result == {task}
    if result:
        await asyncio.wait(result)


@pytest.mark.asyncio
async def test_scope_dispose_cancels_inflight():
    scope = le.Scope.of("cancel_scope")
    started = asyncio.Event()
    cleaned = asyncio.Event()

    with scope.context():

        @le.on(CancelEvent)
        async def handler(foo: str):
            started.set()
            try:
                await asyncio.sleep(10)
            finally:
                cleaned.set()

    task = le.publish(CancelEvent("x"), scope=scope)
    await started.wait()

    dispose_tasks = scope.dispose()
    assert dispose_tasks is not None
    await asyncio.gather(*dispose_tasks, return_exceptions=True)

    assert cleaned.is_set()
    await task


@pytest.mark.asyncio
async def test_disable_does_not_cancel():
    scope = le.Scope.of("disable_scope")
    started = asyncio.Event()
    completed = asyncio.Event()

    with scope.context():

        @le.on(CancelEvent)
        async def handler(foo: str):
            started.set()
            await asyncio.sleep(0.05)
            completed.set()

    task = le.publish(CancelEvent("x"), scope=scope)
    await started.wait()
    scope.disable()  # 软暂停，不应取消 in-flight
    await task
    assert completed.is_set()


@pytest.mark.asyncio
async def test_cancel_one_does_not_cancel_group():
    scope1 = le.Scope.of("cancel_group_1")
    scope2 = le.Scope.of("cancel_group_2")
    slow_started = asyncio.Event()
    slow_cleaned = asyncio.Event()
    fast_done = asyncio.Event()

    with scope1.context():

        @le.on(CancelEvent)
        async def slow(foo: str):
            slow_started.set()
            try:
                await asyncio.sleep(10)
            finally:
                slow_cleaned.set()

    with scope2.context():

        @le.on(CancelEvent)
        async def fast(foo: str):
            await asyncio.sleep(0.01)
            fast_done.set()

    task = le.publish(CancelEvent("x"))
    await slow_started.wait()
    d = scope1.dispose()
    await asyncio.wait_for(fast_done.wait(), 1.0)  # 同组其它订阅者不受连累
    if d:
        await asyncio.gather(*d, return_exceptions=True)
    assert slow_cleaned.is_set()
    await task


@pytest.mark.asyncio
async def test_dispose_cancels_asyncgen():
    scope = le.Scope.of("cancel_asyncgen_scope")
    started = asyncio.Event()
    cleaned = asyncio.Event()

    with scope.context():

        @le.on(CancelEvent)
        async def gen_handler(foo: str):
            started.set()
            try:
                yield foo
                await asyncio.sleep(10)
                yield "never"
            finally:
                cleaned.set()

    task = le.publish(CancelEvent("x"), scope=scope)
    await started.wait()
    await asyncio.sleep(0.01)
    d = scope.dispose()
    if d:
        await asyncio.gather(*d, return_exceptions=True)
    assert cleaned.is_set()
    await task
