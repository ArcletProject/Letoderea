import pytest
from dataclasses import dataclass
import arclet.letoderea as le
from arclet.letoderea import Contexts


class RandomProvider(le.Provider[str]):
    def __init__(self, t: bool = False) -> None:
        self.second_exec = t
        super().__init__()

    async def __call__(self, context: Contexts):
        if not self.second_exec:
            self.second_exec = True
            return "P_dispatcher"
        return "2"


@le.make_event(name="test")
@dataclass
class TestEvent:
    foo: str
    bar: str


@pytest.mark.asyncio
async def test_param_solve():
    from arclet.letoderea.subscriber import CompileParam
    p = CompileParam("p", None, None, [], None, None)
    assert await p.solve({"p": "1"}) == "1"
    pro = RandomProvider()
    p1 = CompileParam("p", None, None, [pro], None, None)
    assert await p1.solve({}) == "P_dispatcher"
    f = CompileParam("f", None, None, [pro], None, None)
    assert await f.solve({}) == "2"


@pytest.mark.asyncio
async def test_unresolve():
    from arclet.letoderea.exceptions import UnresolvedRequirement
    from arclet.letoderea.subscriber import CompileParam, Empty

    p = CompileParam("p", None, Empty, [], None, None)
    with pytest.raises(UnresolvedRequirement):
        await p.solve({})


@pytest.mark.asyncio
async def test_event_dispatch():

    executed = []

    @le.on(TestEvent)
    async def _1(
        foo,
        bar,
        ctx: le.Contexts,
        event: TestEvent,
    ):
        assert foo == "f"
        assert bar == "b"
        assert event.__class__ is TestEvent
        assert ctx["foo"] == "f"
        assert ctx["bar"] == "b"
        executed.append(1)

    await le.publish(TestEvent("f", "b"))

    assert len(executed) == 1


@pytest.mark.asyncio
async def test_external_dispatch():
    executed = []

    le.es.define(int, supplier=lambda x: {"name": str(x)})

    @le.on(int)
    async def s(name: str):
        assert name == "1"
        executed.append(1)

    await le.publish(1)
    assert executed


@pytest.mark.asyncio
async def test_priority():
    executed = []

    @le.use("test", priority=10)
    async def _1():
        executed.append(1)

    @le.use("test", priority=1)
    async def _2():
        executed.append(2)

    await le.publish(TestEvent("f", "b"))
    assert executed == [2, 1]
