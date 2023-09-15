from arclet.letoderea import Publisher, EventSystem, provide, Contexts
import asyncio


loop = asyncio.new_event_loop()
es = EventSystem(loop)


class TestEvent:
    def __init__(self, name: str):
        self.name = name

    async def gather(self, context: Contexts):
        context["name"] = self.name



test = provide(str, call="name")

with Publisher("test", TestEvent, predicate=lambda x: x.name == "hello world") as pub1:
    pub1.bind(test)
    @pub1.register()
    async def test_subscriber1(a: str):
        print(1, a)

with Publisher("test", TestEvent, predicate=lambda x: x.name == "world hello") as pub2:
    pub2.bind(test)

    @pub2.register()
    async def test_subscriber2(a: str):
        print(2, a)

async def main():
    await es.publish(TestEvent("hello world"))
    await es.publish(TestEvent("world hello"))

es.register(pub1, pub2)
loop.run_until_complete(main())
