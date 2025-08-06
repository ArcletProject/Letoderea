import pytest
import arclet.letoderea as le


@le.make_event
class BaseEvent:
    foo: str

    __result_type__ = str


@le.make_event
class DeriveEvent(BaseEvent):
    bar: str

    __publisher__ = "derive"


@pytest.mark.asyncio
async def test_communicate():
    results = []

    @le.on(DeriveEvent)
    async def s1(foo, bar):
        assert foo == "1"
        assert bar == "res_ster"
        res = await le.post(BaseEvent("2"))
        results.append(res)

    @le.on(BaseEvent)
    async def s2(foo):
        assert foo == "2"
        return f"res_{foo}"

    await le.publish(DeriveEvent("1", "res_ster"))
    assert results[0] and results[0].value == "res_2"
    s2.dispose()
    await le.publish(DeriveEvent("1", "res_ster"))
    assert not results[1]


@pytest.mark.asyncio
async def test_result_validate():
    results = []

    @le.on(DeriveEvent)
    async def s1(foo, bar):
        assert foo in ("1", "2")
        assert bar == "res_ster"
        res = await le.post(BaseEvent(foo))
        results.append(res)

    @le.on(BaseEvent)
    async def s2(foo):
        if foo == "2":
            return 12345
        return f"res_{foo}"

    await le.publish(DeriveEvent("1", "res_ster"))
    assert results[0] and results[0].value == "res_1"
    await le.publish(DeriveEvent("2", "res_ster"))
    assert not results[1]


@pytest.mark.asyncio
async def test_inherit():
    event = DeriveEvent("1", "res_ster")

    finish = []

    @le.on(DeriveEvent)
    async def s(ctx: le.Contexts, foo, bar):
        assert foo == "1"
        assert bar == "res_ster"
        await le.publish(BaseEvent("2"), inherit_ctx=ctx.copy())
        finish.append(2)

    @le.on(BaseEvent)
    async def t(event: BaseEvent, foo, bar):
        assert isinstance(event, BaseEvent)
        assert foo == "2"
        assert bar == "res_ster"
        finish.append(1)

    await le.publish(event)

    assert finish == [1, 2]
