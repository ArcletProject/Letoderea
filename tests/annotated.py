from arclet.letoderea import EventSystem
from arclet.letoderea.ref import deref
from typing_extensions import Annotated

es = EventSystem()


class TestEvent:
    type: str = "TestEvent"
    index: int = 0

    async def gather(self, context: dict):
        context['index'] = self.index


@es.on(TestEvent)
async def test(
    index: Annotated[int, "index"],
    a: str = "hello"
):
    print("test:", index, a)


@es.on(TestEvent)
async def test1(
    index: Annotated[int, lambda x: x['index']],
    a: str = "hello"
):
    print("test1:", index, a)


@es.on(TestEvent)
async def test2(
    index: Annotated[int, deref(TestEvent).index],
    a: str = "hello"
):
    print("test2:", index, a)


es.loop.run_until_complete(es.publish(TestEvent()))
