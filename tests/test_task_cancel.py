import asyncio

import pytest

import arclet.letoderea as le
from arclet.letoderea import Subscriber


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
