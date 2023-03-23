import asyncio

from arclet.letoderea import EventSystem, Contexts, wrap_aux
from arclet.letoderea.auxiliary import BaseAuxiliary, SCOPE, AuxType

loop = asyncio.get_event_loop()
es = EventSystem(loop=loop)


class TestDecorate(BaseAuxiliary):

    def __init__(self):
        super().__init__(AuxType.supply)

    async def __call__(self, scope: SCOPE, context: Contexts):
        if scope == "prepare":
            for k, v in context.items():
                if isinstance(v, str):
                    context[k] = v * 2
                if isinstance(v, int):
                    context[k] = v * 3
            return context
        for k, v in context.items():
            if isinstance(v, str):
                context[k] = bytes(v, encoding="utf-8")
        return context
    @property
    def available_scopes(self) -> set[SCOPE]:
        return {"prepare", "complete"}


class ExampleEvent:
    type: str = "ExampleEvent"
    num: int
    msg: str

    async def gather(self, context: dict):
        context['m'] = self.num
        context['a'] = self.msg


@es.register(ExampleEvent)
@wrap_aux(TestDecorate())
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
