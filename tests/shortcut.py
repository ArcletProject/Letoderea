from arclet.letoderea import bypass_if, EventSystem, subscribe, is_event
from arclet.letoderea.ref import deref
from typing_extensions import Annotated

es = EventSystem()


class TestEvent:
    type: str = "TestEvent"
    index: int = 0
    msg: str

    async def gather(self, context: dict):
        context['index'] = self.index
        context['type'] = self.type
        context['msg'] = "hello"

@subscribe()
@bypass_if(lambda x: x['index'] == 0)
@is_event(TestEvent)
async def test(
    index: Annotated[int, "index"],
    a: Annotated[str, deref(TestEvent).msg]
):
    print("enter when index != 0")
    print("test1:", index, a)

@subscribe()
@bypass_if(deref(TestEvent).index != 0)
@is_event(TestEvent)
async def test1(
    index: Annotated[int, deref(TestEvent).index],
    t: Annotated[int, deref(TestEvent).type],
    a: Annotated[str, "msg"]
):
    print("enter when index == 0")
    print("test2:", index, a, t)


async def main():
    e1 = TestEvent()
    e1.index = 0
    await es.publish(e1)
    e2 = TestEvent()
    e2.index = 1
    await es.publish(e2)


es.loop.run_until_complete(main())
