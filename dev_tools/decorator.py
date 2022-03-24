import asyncio
from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent
from arclet.letoderea.entities.auxiliary import BaseAuxiliary
from arclet.letoderea.utils import ArgumentPackage

loop = asyncio.get_event_loop()
test_stack = [0]
es = EventSystem(loop=loop)


class TestDecorate(BaseAuxiliary):
    pass


@TestDecorate.inject_aux("before_parse", "supply")
def supply(target_argument: ArgumentPackage):
    if target_argument.annotation == str:
        return target_argument.value * 2
    if target_argument.annotation == int:
        return target_argument.value * 3


@TestDecorate.inject_aux("parsing", "supply")
def supply(target_argument: ArgumentPackage):
    if target_argument.annotation == str:
        return bytes(target_argument.value, encoding="utf-8")


class ExampleEvent(TemplateEvent):
    type: str = "ExampleEvent"
    num: int
    msg: str

    def get_params(self):
        return self.param_export(
            a=self.msg,
            m=self.num
        )


@es.register(ExampleEvent)
@TestDecorate.set_target()
async def test(m: int, a: str = TestDecorate()):
    print(m, type(m), end=' ')
    print(a, type(a))


async def main():
    a = ExampleEvent()
    a.msg = 'a'
    a.num = 2
    for i in range(6):
        await asyncio.sleep(0.1)
        es.event_publish(a)


loop.run_until_complete(main())
