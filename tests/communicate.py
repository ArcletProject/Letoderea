import asyncio
from dataclasses import dataclass

from arclet.letoderea import es, make_event


@make_event
@dataclass
class TestEvent:
    index: int


@dataclass
class Data:
    query: str

    __result_type__ = str
    __publisher__ = "pluginA"


es.define("pluginA", Data)


@es.on(TestEvent)
async def test(index: int):
    print("test:", index)
    print("send pluginA Data")
    res = await es.post(Data("abcd"))
    if res:
        print("pluginA query res:", res.value)
    else:
        print("pluginA query failed")


async def test1(query: str):
    print("test1 pluginA query:", query)
    return "efgh"


async def test2(query: str):
    print("test2 pluginA query:", query)
    return 1234


async def main():
    sub1 = es.on(Data, test1)
    await es.publish(TestEvent(0))
    await asyncio.sleep(1)
    sub1.dispose()
    sub2 = es.use("pluginA", test2)
    await es.publish(TestEvent(1))
    await asyncio.sleep(1)
    sub2.dispose()
    await es.publish(TestEvent(2))


asyncio.run(main())
