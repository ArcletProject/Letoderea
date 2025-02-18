import pytest

from dataclasses import dataclass
import arclet.letoderea as le


@le.make_event
@dataclass
class TestEvent:
    foo: str


async def as_int(result):
    return int(result)


async def int_when_int(ctx: le.Contexts):
    params = le.params(ctx)
    for param in params:  # pragma: no cover
        if param.annotation is int:
            return {param.name: 1}


@pytest.mark.asyncio
async def test_propagate():
    executed = []

    @le.on(TestEvent)
    async def s(foo: str):
        assert foo == "1"
        executed.append(1)
        return foo

    s.propagate(as_int)
    result = await le.post(TestEvent("1"))

    assert executed
    assert result and result.value == 1


@pytest.mark.asyncio
async def test_prepend_propagate():

    executed = []

    @le.on(TestEvent)
    async def s(bar: int):
        assert bar == 1
        executed.append(1)

    s.propagate(int_when_int, prepend=True)
    await le.publish(TestEvent("1"))

    assert executed


@pytest.mark.asyncio
async def test_prepend_condition():
    executed = []

    @le.on(TestEvent)
    async def s():
        executed.append(1)

    @s.propagate(prepend=True)
    async def _(foo: str):
        executed.append(1)
        if foo == "1":
            return
        return le.STOP

    await le.publish(TestEvent("1"))
    await le.publish(TestEvent("2"))
    assert len(executed) == 3


@pytest.mark.asyncio
async def test_defer():
    executed = []

    async def deferred(foo: str):
        assert foo == "1"
        executed.append(1)

    @le.on(TestEvent)
    async def s():
        le.defer(s, deferred)
        executed.append(1)

    await le.publish(TestEvent("1"))
    assert len(executed) == 2


@pytest.mark.asyncio
async def test_dependency_condition():
    from arclet.letoderea.handler import generate_contexts
    from arclet.letoderea.exceptions import UnresolvedRequirement
    executed = []
    ctx = await generate_contexts(TestEvent("1"))

    @le.on(TestEvent)
    async def s():
        executed.append(1)

    @s.propagate(prepend=True)
    async def p1(bar: int):
        executed.append(2)

    async def p2(foo: str):
        executed.append(3)
        return {"bar": 1}

    dispose = s.propagate(p2, prepend=True)
    await s.handle(ctx.copy())
    assert executed == [3, 2, 1]
    executed.clear()

    dispose()
    with pytest.raises(UnresolvedRequirement):
        await s.handle(ctx.copy())

    s.skip_req_missing = True
    assert await s.handle(ctx.copy()) == le.STOP
    executed.clear()

    @s.propagate(prepend=True, priority=1)
    async def p3():
        return {"bar": 1}

    await s.handle(ctx.copy())
    assert executed == [2, 1]
