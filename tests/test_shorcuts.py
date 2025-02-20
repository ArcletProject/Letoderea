import pytest
from typing import Annotated

from arclet.letoderea import bypass_if, enter_if, es, on
from arclet.letoderea.ref import deref


class TestEvent:
    type: str = "TestEvent"
    flag: bool = False
    msg: str

    async def gather(self, context: dict):
        context["flag"] = self.flag
        context["type"] = self.type
        context["msg"] = "hello"


@pytest.mark.asyncio
async def test_annotated():
    executed = []

    @es.on(TestEvent)
    async def s(flag: Annotated[bool, "flag"]):
        assert flag is False
        executed.append(1)

    def func(x): return x["msg"] + "!"

    @es.on(TestEvent)
    async def s1(a: Annotated[str, func]):
        assert a == "hello!"
        executed.append(1)

    e = TestEvent()
    await es.publish(e)
    assert len(executed) == 2


@pytest.mark.asyncio
async def test_deref():
    executed = []

    @on()
    @enter_if(deref(TestEvent).flag)
    async def s(flag: Annotated[bool, "flag"], a: Annotated[str, deref(TestEvent).msg]):
        assert flag is True
        assert a == "hello"
        executed.append(1)

    @on()
    @bypass_if(deref(TestEvent).flag)
    async def s1(
        flag: Annotated[bool, deref(TestEvent).flag],
        t: Annotated[int, deref(TestEvent).type],
        a: Annotated[str, "msg"]
    ):
        assert flag is False
        assert t == "TestEvent"
        assert a == "hello"
        executed.append(1)

    e1 = TestEvent()
    e1.flag = True
    await es.publish(e1)
    e2 = TestEvent()
    await es.publish(e2)
    assert len(executed) == 2
