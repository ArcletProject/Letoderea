from __future__ import annotations

import asyncio

from arclet.letoderea import Contexts, Depends, es
from arclet.letoderea.exceptions import HandlerStop


class ExampleEvent:
    async def gather(self, context: Contexts):
        context["m"] = "aa"


def test_depend(m: str):
    if m == "aa":
        return True
    raise HandlerStop


def TestDepend() -> bool:
    return Depends(test_depend)


@es.on(ExampleEvent)
def test(m: bool = TestDepend()):
    print(m)


async def main():
    try:
        a = ExampleEvent()
        await es.publish(a)
    except HandlerStop:
        return


asyncio.run(main())
