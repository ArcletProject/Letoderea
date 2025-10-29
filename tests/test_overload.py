import pytest
from typing import Literal, overload
import arclet.letoderea as le


@pytest.mark.asyncio
async def test_overload():
    executed = []

    ol = le.Overloader("test")

    @overload
    @ol.overload
    async def s() -> Literal[0]:
        executed.append((0, None))
        return 0

    @overload
    @ol.overload
    async def s(a: int, b: Literal[True]) -> Literal[1]:
        executed.append((1, a))
        return 1

    @overload
    @ol.overload
    async def s(a: int, b: Literal[False]) -> Literal[2]:
        executed.append((2, b))
        return 2

    @overload
    @ol.overload
    async def s(a: int, *, c: int) -> Literal[3]:
        executed.append((3, c * a))
        return 3

    @ol.define
    async def s(a=None, b=None, c=None):
        pass

    assert await s() == 0
    assert await s(10, True) == 1
    assert await s(20, False) == 2
    assert await s(5, c=4) == 3

    assert executed == [(0, None), (1, 10), (2, False), (3, 20)]
