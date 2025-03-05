import asyncio

import arclet.letoderea as le


async def _supplier(x: int, ctx): ctx.update(name=str(x))
le.define(int, supplier=_supplier)


@le.on(int)
async def test_subscriber(name: str):
    print(name)


async def main():
    await le.publish(1)
    await le.publish(2)


asyncio.run(main())
