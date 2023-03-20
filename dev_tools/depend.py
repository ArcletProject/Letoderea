from __future__ import annotations

from arclet.letoderea import EventSystem
from arclet.letoderea.builtin.depend import Depends
from arclet.letoderea import Contexts
from arclet.letoderea.exceptions import ParsingStop

es = EventSystem()


class ExampleEvent:
    async def gather(self, context: dict):
        context['m'] = 'aa'


def test_depend(m: str):
    if m == 'aa':
        return False
    raise ParsingStop


def TestDepend() -> bool:
    return Depends(test_depend)


@es.register(ExampleEvent)
def test(m: bool = TestDepend()):
    print(m)


async def main():
    try:
        a = ExampleEvent()
        await es.publish(a)
    except ParsingStop:
        return

es.loop.run_until_complete(main())
