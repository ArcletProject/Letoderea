import asyncio

from arclet.letoderea import es, provide


class TestEvent:
    type: str = "TestEvent"
    msg: int = 0

    async def gather(self, context: dict):
        context["index"] = self.msg


@es.on(TestEvent, providers=[provide(int, call="index")])
async def test(
    index: str | int,
    a: str = "hello",
):
    print("test:", index, a)
    # test: 0 hello
    # provide, 'index' -> int -> index: Union[str, int]
    # no provide, a: str = "hello"


@es.on(TestEvent, providers=[provide(int | str, call="index")])
async def test1(
    index: int,
    a: str = "hello",
):
    print("test1:", index, a)
    # test1: 0 0
    # provide, 'index' -> Union[int, str] -> index: int
    # provide, 'index' -> Union[int, str] -> a: str


async def main():
    await es.publish(TestEvent())


asyncio.run(main())
