import pytest
from dataclasses import dataclass
from typing import Annotated


from arclet.letoderea import bypass_if, enter_if, es, on, on_global, provide, param
from arclet.letoderea.ref import deref


class ShortcutEvent:
    type: str = "ShortcutEvent"
    flag: bool = False
    msg: str = "hello"

    async def gather(self, context: dict):
        context["flag"] = self.flag
        context["type"] = self.type
        context["msg"] = self.msg


@dataclass
class User:
    id: int
    name: str


class ShortcutEvent1:
    user: User

    async def gather(self, context: dict):
        context["user"] = self.user

    providers = [provide(User, "user")]


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

    @on_global().if_(deref(ShortcutEvent).flag, 100)
    async def s(flag: Annotated[bool, "flag"]):
        assert flag is True
        executed.append(1)

    @on_global().unless(deref(ShortcutEvent).flag)
    async def s1(
        flag: Annotated[bool, deref(ShortcutEvent).flag],
        t: Annotated[int, deref(ShortcutEvent).type],
        a: str = deref(ShortcutEvent).msg + "a"
    ):
        assert flag is False
        assert t == "ShortcutEvent"
        assert a == "helloa"
        executed.append(1)

    @on_global
    @enter_if & deref(ShortcutEvent).flag & (deref(ShortcutEvent).msg == "world")
    async def s2(flag: Annotated[bool, deref(ShortcutEvent).flag], a: Annotated[str, deref(ShortcutEvent).msg]):
        assert flag is True
        assert a == "world"
        executed.append(1)

    e1 = ShortcutEvent()
    e1.flag = True
    await es.publish(e1)
    e2 = ShortcutEvent()
    await es.publish(e2)
    e3 = ShortcutEvent()
    e3.flag = True
    e3.msg = "world"
    await es.publish(e3)
    assert len(executed) == 4


@pytest.mark.asyncio
async def test_deref_advance():
    executed = []

    @on_global
    @enter_if & (deref(User).name == "test")
    async def s(user: User):
        assert user.name == "test"
        executed.append(1)

    @on_global
    @enter_if & (deref(User).id == 2)
    async def s1(user: User):
        assert user.id == 2
        executed.append(1)

    e4 = ShortcutEvent1()
    e4.user = User(id=1, name="test")
    await es.publish(e4)
    e5 = ShortcutEvent1()
    e5.user = User(id=2, name="test1")
    await es.publish(e5)
    assert len(executed) == 2

    s.dispose()
    s1.dispose()

    @on_global
    @enter_if.priority(20) & (deref(User, "user").id == param("user_id"))
    async def s2(user: User, user_id: int):
        assert user.id == user_id == 3
        executed.append(1)

    @s2.propagate(prepend=True)
    async def _():
        return {"user_id": 3}

    e6 = ShortcutEvent1()
    e6.user = User(id=3, name="test2")
    await es.publish(e6)
    assert len(executed) == 3

    s2.dispose()

    @on_global
    @enter_if & (deref(str, "type") == "ShortcutEvent") & (deref(str, "msg") == "greet_msg")
    async def s3(msg: str, type: str):
        assert type == "ShortcutEvent"
        assert msg == "greet_msg"
        executed.append(1)

    e7 = ShortcutEvent()
    e7.msg = "greet_msg"
    await es.publish(e7)
    assert len(executed) == 4
