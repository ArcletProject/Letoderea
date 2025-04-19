import pytest
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
    from arclet.letoderea.core import run_handler
    from arclet.letoderea.exceptions import UnresolvedRequirement
    from arclet.letoderea.subscriber import CompileParam, Empty

    p = CompileParam("p", None, Empty, [], None, None)
    with pytest.raises(UnresolvedRequirement):
        await p.solve({})

    @le.on(TestEvent, skip_req_missing=False)
    @le.bind(le.provide(int, "age", "a", _id="foo"))
    @le.bind(le.provide(int, "age", "b", _id="bar"))
    @le.bind(le.provide(int, "age", "c", _id="baz"))
    async def s0(foo: str, age: int):  # pragma: no cover
        print(foo, age)

    with pytest.raises(UnresolvedRequirement):
        await run_handler(s0, TestEvent("1", "2"))


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

    @le.gather
    async def _(num: int, ctx):
        return ctx.update(name=str(num))

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


@pytest.mark.asyncio
async def test_exit_state():
    from arclet.letoderea import STOP, ExitState
    executed = []

    @le.on(TestEvent, priority=10)
    async def s_1():
        executed.append(1)

    @le.on(TestEvent, priority=12)
    async def s_2():
        executed.append(2)

    await le.publish(TestEvent("f", "b"))
    assert executed == [1, 2]

    s_1.dispose()
    executed.clear()

    @le.on(TestEvent, priority=10)
    async def s_3():
        executed.append(1)
        return STOP

    await le.publish(TestEvent("f", "b"))
    assert executed == [1, 2]

    s_3.dispose()
    executed.clear()

    @le.on(TestEvent, priority=10)
    async def s_4():
        executed.append(1)
        return ExitState.block

    await le.publish(TestEvent("f", "b"))
    assert executed == [1]

    s_4.dispose()
    executed.clear()

    @le.on(TestEvent, priority=10)
    async def s_5():
        executed.append(0)
        raise STOP

    @le.on(TestEvent, priority=11)
    async def s_6():
        executed.append(1)
        raise ExitState.block

    await le.publish(TestEvent("f", "b"))
    assert executed == [0, 1]
