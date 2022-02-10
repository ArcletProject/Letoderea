import asyncio
from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent
from arclet.letoderea.breakpoint.stepout import StepOut
from arclet.letoderea.breakpoint import Breakpoint

loop = asyncio.get_event_loop()
test_stack = [0]
es = EventSystem(loop=loop)
break_point = Breakpoint(event_system=es)


class TestStepOut(StepOut):

    @staticmethod
    def handler(msg: str):
        if msg == "continue!":
            print(msg)
            return msg


class ExampleEvent(TemplateEvent):
    type: str = "ExampleEvent"
    msg: str

    def get_params(self):
        return self.param_export(
            str=self.msg
        )


@es.register(ExampleEvent)
async def test(m: str):
    if m == 'hello':
        print("wait for msg:'continue!' ")
        await break_point(TestStepOut(ExampleEvent))
        print(m)


a = ExampleEvent()
a.msg = "hello"
b = ExampleEvent()
b.msg = "continue!"


async def main():
    for i in range(0, 4):
        if i % 2 == 0:
            print('>>> event posted with msg: "hello"')
            es.event_spread(a)
        else:
            print('>>> event posted with msg: "continue!"')
            es.event_spread(b)
        await asyncio.sleep(1)


loop.run_until_complete(main())

