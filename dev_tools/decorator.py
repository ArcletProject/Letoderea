import asyncio
from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent
from arclet.letoderea.entities.decorator import TemplateDecorator
from arclet.letoderea.utils import ArgumentPackage

loop = asyncio.get_event_loop()
test_stack = [0]
es = EventSystem(loop=loop)


class TestDecorator(TemplateDecorator):
    def before_parser(self, target_argument: ArgumentPackage) -> str:
        if target_argument.annotation == self.target_type:
            return 4 * target_argument.value

    def after_parser(self, target_argument: ArgumentPackage) -> str:
        if target_argument.annotation == self.supplement_type:
            return 2 * target_argument.value


class ExampleEvent(TemplateEvent):
    type: str = "ExampleEvent"
    msg: str

    def get_params(self):
        return self.param_export(
            str=self.msg
        )


@es.register(ExampleEvent, decorators=[TestDecorator(str, str)])
async def test(m: str):
    for i in range(5):
        await asyncio.sleep(0.1)
        print(m, type(m))
    loop.stop()


a = ExampleEvent()
a.msg = 'a'
es.event_spread(a)
loop.run_forever()
