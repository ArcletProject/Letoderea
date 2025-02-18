import pytest
from dataclasses import dataclass
import arclet.letoderea as le


@le.make_event
@dataclass
class TestEvent1:
    foo: str
    bar: str


@le.make_event
@dataclass
class TestEvent2:
    foo: str

    __result_type__ = str


@pytest.mark.asyncio
async def test_communicate():
    results = []

    @le.on(TestEvent1)
    async def s1(foo, bar):
        assert foo == "1"
        assert bar == "res_ster"
        res = await le.post(TestEvent2("2"))
        results.append(res)

    @le.on(TestEvent2)
    async def s2(foo):
        assert foo == "2"
        return f"res_{foo}"

    await le.publish(TestEvent1("1", "res_ster"))
    assert results[0] and results[0].value == "res_2"
    s2.dispose()
    await le.publish(TestEvent1("1", "res_ster"))
    assert not results[1]


@pytest.mark.asyncio
async def test_inherit():
    event = TestEvent1("1", "res_ster")

    finish = []

    @le.on(TestEvent1)
    async def s(ctx: le.Contexts, foo, bar):
        assert foo == "1"
        assert bar == "res_ster"
        le.publish(TestEvent2("2"), inherit_ctx=ctx.copy())

    @le.on(TestEvent2)
    async def t(event: TestEvent2, foo, bar):
        assert isinstance(event, TestEvent2)
        assert foo == "2"
        assert bar == "res_ster"
        finish.append(1)

    await le.publish(event)

    assert finish
