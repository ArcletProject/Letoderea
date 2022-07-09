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
            print("[out] >>> receive in handler", msg)
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
        print("[subscriber] >>> wait for msg:'continue!' ")
        out = TestStepOut(ExampleEvent)
        print("[subscriber] >>> current out:", out)
        await break_point(out)
        print("[subscriber] >>>", m)


a = ExampleEvent()
a.msg = "hello"
b = ExampleEvent()
b.msg = "continue!"
c = ExampleEvent()
c.msg = "wait"


async def main():
    for i in range(0, 6):
        if i % 3 == 0:
            print('>>> event posted with msg: "hello"')
            es.event_publish(a)
        elif (i - 1) % 3 == 0:
            print('>>> event posted with msg: "wait"')
            es.event_publish(c)
        else:
            print('>>> event posted with msg: "continue!"')
            es.event_publish(b)
        await asyncio.sleep(1)


loop.run_until_complete(main())
