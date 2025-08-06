import asyncio

from arclet.letoderea import es, make_event


@make_event
class TestEvent:
    name: str

    def __init__(self, name: str):
        self.name = name


@es.on(TestEvent)
async def subscriber1(name: str):
    print(name)


es.set_event_loop(loop := asyncio.new_event_loop())
es.publish(TestEvent("hello world"))
es.publish(TestEvent("world hello"))


async def main():
    await asyncio.sleep(1)


loop.run_until_complete(main())
