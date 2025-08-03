import asyncio
from contextlib import contextmanager, asynccontextmanager
from datetime import datetime
from typing import Any

import pytest
import arclet.letoderea as le


@le.make_event
class PropagateEvent:
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

    @le.on(PropagateEvent)
    async def s(foo: str):
        assert foo in ("1", "2")
        executed.append(1)
        return foo

    s.propagate(as_int)

    @s.propagate()
    async def _(result):
        if result > 1:
            return le.STOP
        executed.append(1)
        return result

    ans = await le.post(PropagateEvent("1"))
    assert executed
    assert ans and ans.value == 1

    executed.clear()
    ans = await le.post(PropagateEvent("2"))
    assert executed
    assert not ans

    assert s.get_propagator(as_int).callable_target is as_int


@pytest.mark.asyncio
async def test_context_manager():
    executed = []

    @le.on(PropagateEvent)
    async def s(foo: str, bar: int):
        assert foo == "1"
        assert bar == 1
        executed.append(2)

    @s.propagate(prepend=True)
    @asynccontextmanager
    async def _(foo: str):
        assert foo == "1"
        executed.append(1)
        yield {"bar": 1}
        executed.append(3)

    @s.propagate(prepend=True)
    @contextmanager
    def _(foo: str):
        assert foo == "1"
        executed.append(1)
        yield
        executed.append(4)

    await le.publish(PropagateEvent("1"))
    assert executed == [1, 1, 2, 4, 3]


@pytest.mark.asyncio
async def test_prepend_propagate():

    executed = []

    @le.on(PropagateEvent)
    async def s(bar: int):
        assert bar == 1
        executed.append(1)

    s.propagate(int_when_int, prepend=True)
    await le.publish(PropagateEvent("1"))

    assert executed


@pytest.mark.asyncio
async def test_prepend_condition():
    executed = []

    @le.on(PropagateEvent)
    async def s():
        executed.append(1)

    @s.propagate(prepend=True)
    async def _(foo: str):
        executed.append(1)
        if foo == "1":
            return
        return le.STOP

    await le.publish(PropagateEvent("1"))
    await le.publish(PropagateEvent("2"))
    assert len(executed) == 3


@pytest.mark.asyncio
async def test_defer():
    executed = []

    async def deferred(foo: str):
        assert foo == "1"
        executed.append(1)

    @le.on(PropagateEvent)
    async def s():
        le.defer(s, deferred)
        executed.append(1)

    await le.publish(PropagateEvent("1"))
    assert len(executed) == 2


@pytest.mark.asyncio
async def test_dependency_condition():
    from arclet.letoderea.typing import generate_contexts
    from arclet.letoderea.exceptions import UnresolvedRequirement
    executed = []
    ctx = await generate_contexts(PropagateEvent("1"))

    @le.on(PropagateEvent)
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


class Interval(le.Propagator):
    def __init__(self, interval: float):
        self.interval = interval
        self.last_time = None
        self.success = True

    async def before(self):
        if self.last_time is not None:
            self.success = (datetime.now() - self.last_time).total_seconds() > self.interval
            if not self.success:
                return le.STOP
        return {"last_time": self.last_time}

    async def after(self):
        self.last_time = datetime.now()

    def compose(self):
        yield self.before, True
        yield self.after, False


@pytest.mark.asyncio
async def test_propagator():
    executed = []

    class MyPropagator(le.Propagator):
        def compose(self):
            yield lambda: executed.append(1), True
            yield Interval(0.3)

    @le.on(PropagateEvent)
    @le.propagate(MyPropagator())
    async def s(last_time, foo: str):
        assert last_time is None or isinstance(last_time, datetime)
        executed.append(foo)

    await le.publish(PropagateEvent("1"))
    await asyncio.sleep(0.2)
    await le.publish(PropagateEvent("2"))
    await asyncio.sleep(0.2)
    await le.publish(PropagateEvent("3"))

    assert executed == [1, "1", 1, 1, "3"]
    assert s.get_propagator(Interval).success


@pytest.mark.asyncio
async def test_dependency_condition2():
    from arclet.letoderea.typing import generate_contexts
    from arclet.letoderea.exceptions import UnresolvedRequirement, ProviderUnsatisfied
    executed = []
    ctx = await generate_contexts(PropagateEvent("123 456"))

    class ProgProvider(le.Provider[Any]):
        def __init__(self, type_: str):
            self.type_ = type_
            super().__init__()

        async def __call__(self, context: le.Contexts):
            if "info" not in context:
                raise ProviderUnsatisfied("info")
            if self.type_ == "len":
                return context["info"]["len"]
            else:
                return context["info"]["parts"]

    class ProgFactory(le.ProviderFactory):
        def validate(self, param: le.Param):
            if param.annotation is int:
                return ProgProvider("len")
            elif param.annotation is list:
                return ProgProvider("parts")

    @le.on(PropagateEvent, providers=[ProgFactory()])
    async def s1(bar: int, parts: list):
        assert bar == 7
        assert parts == ["123", "456"]
        executed.append(1)

    @s1.propagate(prepend=True)
    async def p2(bar: int):
        executed.append(bar)

    @s1.propagate(prepend=True)
    async def p1(foo: str):
        executed.append(2)
        return {"info": {"len": len(foo), "parts": foo.split()}}



    await s1.handle(ctx.copy())
    assert executed == [2, 7, 1]
