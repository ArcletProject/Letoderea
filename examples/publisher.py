import asyncio

from arclet.letoderea import Contexts, es, define, provide


class TestEvent:
    def __init__(self, name: str):
        self.name = name

    async def gather(self, context: Contexts):
        context["name"] = self.name

    providers = [provide(str, call="name")]


pub = define(TestEvent, name="test")


@es.use(pub)
async def subscriber1(a: str):
    print(a)


async def main():
    await es.publish(TestEvent("hello world"))
    await es.publish(TestEvent("world hello"))


asyncio.run(main())
