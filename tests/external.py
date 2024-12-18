import asyncio

from arclet.letoderea import es

with es.define("pub1", int, predicate=lambda x: x == 1) as pub1:

    async def test_subscriber1(event: int):
        print(event == 1)

    pub1 += test_subscriber1


with es.define("pub2", int, lambda x: {"name": str(x)}) as pub2:

    async def test_subscriber2(name: str):
        print(name)

    pub2 += test_subscriber2


async def main():
    await es.publish(1)
    await es.publish(2)


asyncio.run(main())
