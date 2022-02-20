from datetime import datetime
from arclet.letoderea.entities.auxiliary import BaseAuxiliary
import asyncio
from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent


loop = asyncio.get_event_loop()
test_stack = [0]
es = EventSystem(loop=loop)

#
# class TestCondition(TemplateCondition):
#

#
#     def judge(self, *args, **kwargs) -> bool:
#         now = datetime.now()
#         return now > datetime(year=now.year, month=now.month, day=now.day, hour=self.hour, minute=self.minute)


class TestTimeLimit(BaseAuxiliary):
    def __init__(self, hour, minute):
        self.hour = hour
        self.minute = minute

        @self.set_aux("before_parse", "judge")
        def judge(*args):
            now = datetime.now()
            return now > datetime(year=now.year, month=now.month, day=now.day, hour=self.hour, minute=self.minute)


class TestInterval(BaseAuxiliary):
    def __init__(self, interval: float):
        self.record = False
        self.success = False
        self.last_time = datetime.now()
        self.interval = interval

        @self.set_aux("before_parse", "judge")
        def judge(*args):
            if self.record:
                self.success = result = (datetime.now() - self.last_time).total_seconds() > self.interval
                return result

        @self.set_aux("execution_complete", "judge")
        def judge(*args):
            if not self.record:
                self.last_time = datetime.now()
                self.record = True
                return True
            if self.success:
                self.last_time = datetime.now()
                return True


class ExampleEvent(TemplateEvent):
    type: str = "ExampleEvent"
    msg: int = 0

    def get_params(self):
        return self.param_export(
            int=self.msg
        )


@es.register(ExampleEvent, auxiliaries=[TestInterval(0.3)])
async def test(int: int, a: str = "hello", ):
    print(int, a)


b = ExampleEvent()


async def main():
    for i in range(11):
        await asyncio.sleep(0.1)
        b.msg += 1
        es.event_publish(b)

loop.run_until_complete(main())
