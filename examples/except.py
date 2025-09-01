import asyncio

from arclet.letoderea import Contexts, bind, es, on, provide


class TestEvent:
    async def gather(self, context: Contexts):
        context["name"] = "Letoderea"


@on(TestEvent)
@bind(provide(int, "age", "a", _id="foo"))
@bind(provide(int, "age", "b", _id="bar"))
@bind(provide(int, "age", "c", _id="baz"))
async def subscriber(name: str, age: int):
    print(name, age)


async def main():
    await es.publish(TestEvent())


asyncio.run(main())
