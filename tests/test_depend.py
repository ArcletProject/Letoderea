import pytest
import random
import arclet.letoderea as le
from contextlib import asynccontextmanager
from typing import Annotated


@le.make_event
class TestDependEvent:
    foo: str


async def dep(foo: str, p: int):
    return f"{foo}+{p}"


@le.depends(cache=True)
async def dep1(foo: str):
    return f"{foo}+{random.randint(1, 10)}"


@pytest.mark.asyncio
async def test_depend():

    executed = []

    dep_ = le.Depends(dep)

    @le.on(TestDependEvent, providers=[le.provide(int, "p", call=lambda _: 1)])
    async def s(ster=dep_):
        assert ster == "1+1"
        executed.append(1)

    @le.on(TestDependEvent)
    async def s1(a=dep1, b=dep1):
        assert a == b == "1+2"
        executed.append(1)

    @le.on(TestDependEvent)
    async def s2(a=dep1):
        assert a == "1+2"
        executed.append(1)

    @le.on(TestDependEvent, providers=[le.provide(int, "p", call=lambda _: 3)])
    async def s3(a: Annotated[str, dep_]):
        assert a == "1+3"
        executed.append(1)

    random.seed(42)

    await le.publish(TestDependEvent("1"))
    assert len(executed) == 4


@pytest.mark.asyncio
async def test_context_depend():

    executed = []

    @asynccontextmanager
    async def _mgr():
        executed.append(1)
        try:
            yield 2
        finally:
            executed.append(3)

    async def dep2(foo: str, ctx: le.Contexts):
        stack = ctx[le.STACK]
        ans = await stack.enter_async_context(_mgr())
        assert ans == 2
        return f"{foo}+{ans}"

    @le.on(TestDependEvent)
    async def s4(a=le.Depends(dep2)):
        assert a == "1+2"
        executed.append(2)

    await le.publish(TestDependEvent("1"))
    assert len(executed) == 3
    assert executed == [1, 2, 3]


@pytest.mark.asyncio
async def test_param_depend():

    executed = []

    @le.on(TestDependEvent)
    async def s5(bar: str = le.param("foo", str), foo=le.param("aaa", int, 123)):
        assert bar == "2"
        assert foo == 123
        executed.append(1)

    await le.publish(TestDependEvent("2"))
    assert len(executed) == 1
