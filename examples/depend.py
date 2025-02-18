from __future__ import annotations

import asyncio

from arclet.letoderea import Contexts, Depends, es, STOP


class ExampleEvent:
    async def gather(self, context: Contexts):
        context["m"] = "aa"


def test_depend(m: str):
    if m == "aa":
        return True
    return STOP


def TestDepend() -> bool:
    return Depends(test_depend)


@es.on(ExampleEvent)
def test(m: bool = TestDepend()):
    print(m)


async def main():
    a = ExampleEvent()
    await es.publish(a)


asyncio.run(main())
