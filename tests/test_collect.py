import pytest
from typing import Union
import arclet.letoderea as le


@pytest.mark.asyncio
async def test_collect():
    executed = []

    @le.collect
    async def s0(event):
        executed.append((0, event))

    @le.collect
    async def s1(a: int, b: Union[int, str]):
        executed.append((1, b * a))

    @le.collect
    async def s2(a: int, b: int):
        executed.append((2, b * a))

    @le.collect
    async def s3(a: int, c: int):
        executed.append((3, c * a))

    await le.publish((1,))
    assert executed == [(0, (1,))]
    executed.clear()
    await le.publish((2, "2"))
    assert executed == [(0, (2, "2")), (1, "22")]
    executed.clear()
    await le.publish((3, 3))
    assert executed == [(0, (3, 3)), (1, 9), (2, 9), (3, 9)]
    executed.clear()
    await le.publish({"a": 4, "c": 4})
    assert executed == [(0, {"a": 4, "c": 4}), (3, 16)]
    executed.clear()
    await le.publish({"b": 4, "d": 4})
    assert executed == [(0, {"b": 4, "d": 4})]
