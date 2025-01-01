import asyncio

from arclet.letoderea import make_event, es


@make_event
class TestEvent:
    name: str

    def __init__(self, name: str):
        self.name = name


@es.on(TestEvent)
async def test_subscriber1(name: str):
    print(name)


es.loop = asyncio.new_event_loop()
es.publish(TestEvent("hello world"))
es.publish(TestEvent("world hello"))


async def main():
    await asyncio.sleep(1)

es.loop.run_until_complete(main())
