from __future__ import annotations

import asyncio

from arclet.letoderea import EventSystem
from arclet.letoderea import Depends
from arclet.letoderea import Contexts
from arclet.letoderea.exceptions import ParsingStop

es = EventSystem()


class ExampleEvent:
    async def gather(self, context: Contexts):
        context['m'] = 'aa'


def test_depend(m: str):
    if m == 'aa':
        return False
    raise ParsingStop


def TestDepend() -> bool:
    return Depends(test_depend)


@es.on(ExampleEvent)
def test(m: bool = TestDepend()):
    print(m)


async def main():
    try:
        a = ExampleEvent()
        await es.publish(a)
    except ParsingStop:
        return

asyncio.run(main())
