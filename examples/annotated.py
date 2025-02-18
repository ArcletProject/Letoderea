import asyncio
from typing_extensions import Annotated

from arclet.letoderea import es
from arclet.letoderea.ref import deref


class TestEvent:
    type: str = "TestEvent"
    index: int = 0

    async def gather(self, context: dict):
        context["index"] = self.index


@es.on(TestEvent)
async def test(index: Annotated[int, "index"], a: str = "hello"):
    print("test:", index, a)


@es.on(TestEvent)
async def test1(index: Annotated[int, lambda x: x["index"]], a: str = "hello"):
    print("test1:", index, a)


@es.on(TestEvent)
async def test2(index: Annotated[int, deref(TestEvent).index], a: str = "hello"):
    print("test2:", index, a)


async def main():
    await es.publish(TestEvent())


asyncio.run(main())
