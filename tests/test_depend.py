import pytest

from dataclasses import dataclass
import arclet.letoderea as le


@le.make_event
@dataclass
class TestDependEvent:
    foo: str


async def dep(foo: str, p: int):
    return f"{foo}+{p}"


@pytest.mark.asyncio
async def test_depend():

    executed = []

    @le.on(TestDependEvent, providers=[le.provide(int, "p", call=lambda _: 1)])
    async def s(ster=le.Depends(dep)):
        assert ster == "1+1"
        executed.append(1)

    depend = le.Depends(dep, cache=True)

    @le.depends()
    async def dep1(foo: str, p: int):
        return f"{foo}-{p}"

    @le.on(TestDependEvent, providers=[le.provide(int, "p", call=lambda _: 1)])
    async def s1(a=depend, b=depend, c=dep1):
        assert a == b == "1+1"
        assert c == "1-1"
        executed.append(1)

    for _ in range(5):
        await le.publish(TestDependEvent("1"))

    assert len(executed) == 10
