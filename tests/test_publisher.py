from arclet.letoderea import accept, EventSystem, provide, Contexts
import asyncio


loop = asyncio.new_event_loop()
es = EventSystem(loop)


class TestEvent:
    def __init__(self, name: str):
        self.name = name

    async def gather(self, context: Contexts):
        context["name"] = self.name



test = provide(str, call="name")

with accept("test", TestEvent).context() as pub:
    pub.add_provider(test)

    @es.on(TestEvent)
    async def test_subscriber(a: str):
        print(a)

    async def main():
        await pub.publish(TestEvent("hello world"))


loop.run_until_complete(main())
