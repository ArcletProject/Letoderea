import pytest

from dataclasses import dataclass
import arclet.letoderea as le


@le.make_event
@dataclass
class TestEvent:
    foo: str


async def dep(foo: str, p: int):
    return f"{foo}+{p}"


@pytest.mark.asyncio
async def test_depend():

    executed = []

    @le.on(TestEvent, providers=[le.provide(int, "p", call=lambda _: 1)])
    async def s(ster=le.Depends(dep)):
        assert ster == "1+1"
        executed.append(1)

    depend = le.Depends(dep, cache=True)

    @le.on(TestEvent, providers=[le.provide(int, "p", call=lambda _: 1)])
    async def s1(a=depend, b=depend):
        assert a == b == "1+1"
        executed.append(1)

    for _ in range(5):
        await le.publish(TestEvent("1"))

    assert len(executed) == 10
