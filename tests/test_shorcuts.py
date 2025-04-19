import pytest
from typing import Annotated

from arclet.letoderea import bypass_if, enter_if, es, on, on_global
from arclet.letoderea.ref import deref


class ShortcutEvent:
    type: str = "ShortcutEvent"
    flag: bool = False
    msg: str

    async def gather(self, context: dict):
        context["flag"] = self.flag
        context["type"] = self.type
        context["msg"] = "hello"


@pytest.mark.asyncio
async def test_annotated():
    executed = []

    @on(ShortcutEvent)
    async def s(flag: Annotated[bool, "flag"]):
        assert flag is False
        executed.append(1)

    def func(x): return x["msg"] + "!"

    @on(ShortcutEvent)
    async def s1(a: Annotated[str, func]):
        assert a == "hello!"
        executed.append(1)

    e = ShortcutEvent()
    await es.publish(e)
    assert len(executed) == 2


@pytest.mark.asyncio
async def test_deref():
    executed = []

    @on_global
    @enter_if(deref(ShortcutEvent).flag)
    async def s(flag: Annotated[bool, "flag"], a: Annotated[str, deref(ShortcutEvent).msg]):
        assert flag is True
        assert a == "hello"
        executed.append(1)

    @on_global
    @bypass_if(deref(ShortcutEvent).flag)
    async def s1(
        flag: Annotated[bool, deref(ShortcutEvent).flag],
        t: Annotated[int, deref(ShortcutEvent).type],
        a: Annotated[str, "msg"]
    ):
        assert flag is False
        assert t == "ShortcutEvent"
        assert a == "hello"
        executed.append(1)

    e1 = ShortcutEvent()
    e1.flag = True
    await es.publish(e1)
    e2 = ShortcutEvent()
    await es.publish(e2)
    assert len(executed) == 2
