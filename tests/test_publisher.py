import asyncio

from arclet.letoderea import Contexts, es, provide


class TestEvent:
    def __init__(self, name: str):
        self.name = name

    async def gather(self, context: Contexts):
        context["name"] = self.name


test = provide(str, call="name")

with es.define("test", predicate=lambda x: x.name == "hello world") as pub1:
    pub1.bind(test)

    async def test_subscriber1(a: str):
        print(1, a)

    pub1 += test_subscriber1

with es.define("test", TestEvent, predicate=lambda x: x.name == "world hello"):
    @es.use(providers=[test])
    async def test_subscriber2(a: str):
        print(2, a)


async def main():
    await es.publish(TestEvent("hello world"))
    await es.publish(TestEvent("world hello"))


asyncio.run(main())
