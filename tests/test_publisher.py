import asyncio

from arclet.letoderea import Contexts, auxilia, es, provide


class TestEvent:
    def __init__(self, name: str):
        self.name = name

    async def gather(self, context: Contexts):
        context["name"] = self.name


test = provide(str, call="name")
pub = es.define(TestEvent, "test")
pub.bind(test)


@es.use(pub)
async def test_subscriber1(a: str):
    print(a)


async def main():
    await es.publish(TestEvent("hello world"))
    await es.publish(TestEvent("world hello"))


asyncio.run(main())
