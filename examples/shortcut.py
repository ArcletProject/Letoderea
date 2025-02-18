import asyncio
from typing_extensions import Annotated

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


@on()
@enter_if(deref(TestEvent).flag)
# @is_event(TestEvent)
async def test(flag: Annotated[bool, "flag"], a: Annotated[str, deref(TestEvent).msg]):
    print("enter when flag is True")
    print("test1:", flag, a)


@on()
@bypass_if(deref(TestEvent).flag)
# @is_event(TestEvent)
async def test1(
    flag: Annotated[bool, deref(TestEvent).flag], t: Annotated[int, deref(TestEvent).type], a: Annotated[str, "msg"]
):
    print("enter when flag is False")
    print("test2:", flag, a, t)


async def main():
    e1 = TestEvent()
    e1.flag = True
    await es.publish(e1)
    e2 = TestEvent()
    await es.publish(e2)


asyncio.run(main())
