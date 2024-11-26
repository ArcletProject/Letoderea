import asyncio
from dataclasses import dataclass
from arclet.letoderea import Publisher, make_event


@make_event
@dataclass
class TestEvent:
    index: int


@make_event
@dataclass
class PluginEventA:
    query: str


plugin_publisher = Publisher("plugin_publisher", PluginEventA)
test_publisher = Publisher("test_publisher", TestEvent)


async def test(index: int):
    print("test:", index)
    print("send PluginEventA for query")
    res = await plugin_publisher.bail(PluginEventA("query"))
    print("PluginEventA res:", res)


async def test1(query: str):
    print("test1:", query)
    return "res"


async def main():
    test_publisher.register(test)
    sub = plugin_publisher.register(test1)
    await test_publisher.emit(TestEvent(0))
    await asyncio.sleep(1)
    sub.dispose()
    await test_publisher.emit(TestEvent(1))


asyncio.run(main())