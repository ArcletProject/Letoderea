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
