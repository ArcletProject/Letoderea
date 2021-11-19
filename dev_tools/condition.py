from datetime import datetime
from arclet.letoderea.entities.condition import TemplateCondition
import asyncio
from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent


loop = asyncio.get_event_loop()
test_stack = [0]
es = EventSystem(loop=loop)


class TestCondition(TemplateCondition):

    def __init__(self, hour, minute):
        self.hour = hour
        self.minute = minute

    def judge(self) -> bool:
        now = datetime.now()
        return now > datetime(year=now.year, month=now.month, day=now.day, hour=self.hour, minute=self.minute)


class ExampleEvent(TemplateEvent):
    type: str = "ExampleEvent"
    msg: int

    def get_params(self):
        return self.param_export(
            int=self.msg
        )


@es.register(ExampleEvent, conditions=[TestCondition(23, 30)])
async def test(a: str = "hello"):
    for i in range(5):
        await asyncio.sleep(0.1)
        print(a)
    loop.stop()


b = ExampleEvent()
b.msg = 1
es.event_spread(b)
loop.run_forever()

