from datetime import datetime
from arclet.letoderea.entities.auxiliary import BaseAuxiliary
import asyncio
from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent
import gc

loop = asyncio.get_event_loop()
test_stack = [0]
es = EventSystem(loop=loop)


class TestTimeLimit(BaseAuxiliary):
    def __init__(self, hour, minute):
        self.hour = hour
        self.minute = minute
        super().__init__()


@TestTimeLimit.inject_aux("before_parse", "judge")
def judge(self: TestTimeLimit, *args):
    now = datetime.now()
    return now >= datetime(year=now.year, month=now.month, day=now.day, hour=self.hour, minute=self.minute)


class Interval(BaseAuxiliary):
    def __init__(self, interval: float):
        self.success = True
        self.last_time = datetime.now()
        self.interval = interval
        super().__init__()


@Interval.inject_aux("before_parse", "judge")
def judge(self: Interval, *args):
    self.success = (datetime.now() - self.last_time).total_seconds() > self.interval
    return self.success


@Interval.inject_aux("execution_complete", "judge")
def judge(self: Interval, *args):
    if self.success:
        self.last_time = datetime.now()
        return True


class ExampleEvent(TemplateEvent):
    type: str = "ExampleEvent"
    msg: int = 0

    def get_params(self):
        return self.param_export(
            index=self.msg
        )


@es.register(ExampleEvent, auxiliaries=[TestTimeLimit(9, 0), Interval(0.2)])
async def test(index: int, a: str = "hello", ):
    gc.collect()
    print(index, a)


b = ExampleEvent()


async def main():
    for i in range(11):
        await asyncio.sleep(0.15)
        b.msg += 1
        es.event_publish(b)


loop.run_until_complete(main())
