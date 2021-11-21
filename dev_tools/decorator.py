import asyncio
from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent
from arclet.letoderea.entities.decorator import EventDecorator
from arclet.letoderea.utils import ArgumentPackage

loop = asyncio.get_event_loop()
test_stack = [0]
es = EventSystem(loop=loop)


class TestEventDecorator(EventDecorator):

    def supply(self, target_argument: ArgumentPackage):
        if target_argument.annotation == str:
            return target_argument.value * 2
        if target_argument.annotation == int:
            return target_argument.value * 3


class ExampleEvent(TemplateEvent):
    type: str = "ExampleEvent"
    num: int
    msg: str

    def get_params(self):
        return self.param_export(
            str=self.msg,
            int=self.num
        )


@es.register(ExampleEvent, decorators=[TestEventDecorator()])
async def test(m: int, a: str):
    for i in range(5):
        await asyncio.sleep(0.1)
        print(m, type(m), end=' ')
        print(a, type(a))
    loop.stop()


a = ExampleEvent()
a.msg = 'a'
a.num = 1
es.event_spread(a)
loop.run_forever()
