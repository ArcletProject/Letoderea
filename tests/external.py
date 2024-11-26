import asyncio

from arclet.letoderea import EventSystem

es = EventSystem()


with es.define(int, predicate=lambda x: x == 1) as pub1:

    async def test_subscriber1(event: int):
        print(event == 1)

    pub1 += test_subscriber1


with es.define(int, lambda x: {"name": str(x)}) as pub2:

    async def test_subscriber2(name: str):
        print(name)

    pub2 += test_subscriber2


async def main():
    await es.post(1)
    await es.post(2)


asyncio.run(main())
