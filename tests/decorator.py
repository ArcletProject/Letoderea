import asyncio

from arclet.letoderea import EventSystem, bind
from arclet.letoderea.auxiliary import AuxType, BaseAuxiliary, Scope, Interface

es = EventSystem()


class TestDecorate(BaseAuxiliary):

    def __init__(self):
        super().__init__(AuxType.supply)

    async def __call__(self, scope: Scope, interface: Interface):
        if scope == Scope.prepare:
            ans = {}
            for k, v in interface.ctx.items():
                if isinstance(v, str):
                    ans[k] = v * 2
                if isinstance(v, int):
                    ans[k] = v * 3
            return interface.update(**ans)
        ans = {}
        for k, v in interface.ctx.items():
            if isinstance(v, str):
                ans[k] = bytes(v, encoding="utf-8")
        return interface.update(**ans)

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare, Scope.complete}


class ExampleEvent:
    type: str = "ExampleEvent"
    num: int
    msg: str

    async def gather(self, context: dict):
        context["m"] = self.num
        context["a"] = self.msg


@es.on(ExampleEvent)
@bind(TestDecorate())
async def test(m: int, a: str):
    print(m, type(m), end=" ")
    print(a, type(a))


async def main():
    a = ExampleEvent()
    a.msg = "a"
    a.num = 2
    for _ in range(6):
        await asyncio.sleep(0.1)
        await es.publish(a)


asyncio.run(main())
