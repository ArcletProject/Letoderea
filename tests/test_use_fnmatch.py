import pytest
import arclet.letoderea as le


@le.make_event(name="use_event")
class BaseEvent:
    foo: str
    bar: str


@le.make_event(name="use_event/A")
class DeriveEventA(BaseEvent):
    bar: str = "A"


@le.make_event(name="use_event/B")
class DeriveEventB(BaseEvent):
    bar: str = "B"


@le.make_event(name="use_event/C")
class DeriveEventC(BaseEvent):
    bar: str = "C"


@pytest.mark.asyncio
async def test_fnmatch():
    results = []

    @le.use("use_event/*")
    async def _(foo, bar):
        results.append((foo, bar))

    await le.publish(DeriveEventA("1"))
    await le.publish(DeriveEventB("2"))
    await le.publish(DeriveEventC("3"))

    assert results == [("1", "A"), ("2", "B"), ("3", "C")]
