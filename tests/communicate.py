import asyncio
from typing import TypedDict
from dataclasses import dataclass
from arclet.letoderea import es, make_event


@make_event
@dataclass
class TestEvent:
    index: int


class Data(TypedDict):
    query: str


es.define("pluginA", Data)


@es.on(TestEvent)
async def test(index: int):
    print("test:", index)
    print("send pluginA Data")
    res = await es.post({"query": "abcd"})
    if res:
        print("pluginA query res:", res.value)
    else:
        print("pluginA query failed")


@es.use("pluginA")
async def test1(query: str):
    print("pluginA query:", query)
    return "efgh"


async def main():
    await es.publish(TestEvent(0))
    await asyncio.sleep(1)
    test1.dispose()
    await es.publish(TestEvent(1))


asyncio.run(main())