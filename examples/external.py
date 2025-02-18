import asyncio

from arclet.letoderea import es

es.define(int, supplier=lambda x: {"name": str(x)})


@es.on(int)
async def test_subscriber(name: str):
    print(name)


async def main():
    await es.publish(1)
    await es.publish(2)


asyncio.run(main())
