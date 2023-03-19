import asyncio
from arclet.letoderea import EventSystem, Contexts
from arclet.letoderea.auxiliary import BaseAuxiliary, Scope, AuxType


loop = asyncio.get_event_loop()
es = EventSystem(loop=loop)


class TestDecorate(BaseAuxiliary):
    pass


@TestDecorate.inject(Scope.before_parse, AuxType.supply)
def supply(self: TestDecorate, context: Contexts):
    for k, v in context.items():
        if isinstance(v, str):
            context[k] = v * 2
        if isinstance(v, int):
            context[k] = v * 3


@TestDecorate.inject(Scope.parsing, AuxType.supply)
def supply(self: TestDecorate, context: Contexts):
    for k, v in context.items():
        if isinstance(v, str):
            return bytes(v, encoding="utf-8")


class ExampleEvent:
    type: str = "ExampleEvent"
    num: int
    msg: str

    async def gather(self, context: dict):
        context['m'] = self.num
        context['a'] = self.msg


@es.register(ExampleEvent)
@TestDecorate.wrap()
async def test(m: int, a: str = TestDecorate()):
    print(m, type(m), end=' ')
    print(a, type(a))


async def main():
    a = ExampleEvent()
    a.msg = 'a'
    a.num = 2
    for _ in range(6):
        await asyncio.sleep(0.1)
        await es.publish(a)


loop.run_until_complete(main())
