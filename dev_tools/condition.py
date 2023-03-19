from datetime import datetime
from arclet.letoderea.auxiliary import BaseAuxiliary, Scope, AuxType
import asyncio
from arclet.letoderea import EventSystem
import gc

loop = asyncio.get_event_loop()
test_stack = [0]
es = EventSystem(loop=loop)


class TestTimeLimit(BaseAuxiliary):
    def __init__(self, hour, minute):
        self.hour = hour
        self.minute = minute
        super().__init__()


@TestTimeLimit.inject(Scope.before_parse, AuxType.judge)
def judge(self: TestTimeLimit, event):
    now = datetime.now()
    return now >= datetime(year=now.year, month=now.month, day=now.day, hour=self.hour, minute=self.minute)


class Interval(BaseAuxiliary):
    def __init__(self, interval: float):
        self.success = True
        self.last_time = datetime.now()
        self.interval = interval
        super().__init__()


@Interval.inject(Scope.before_parse, AuxType.judge)
def judge(self: Interval, event):
    self.success = (datetime.now() - self.last_time).total_seconds() > self.interval
    return self.success


@Interval.inject(Scope.cleanup, AuxType.judge)
def judge(self: Interval, event):
    if self.success:
        self.last_time = datetime.now()
        return True


class ExampleEvent:
    type: str = "ExampleEvent"
    msg: int = 0

    async def gather(self, context: dict):
        context['index'] = self.msg


@es.register(ExampleEvent, auxiliaries=[TestTimeLimit(0, 0), Interval(0.2)])
async def test(index: int, a: str = "hello", ):
    gc.collect()
    print(index, a)


b = ExampleEvent()


async def main():
    for _ in range(11):
        await asyncio.sleep(0.15)
        b.msg += 1
        await es.publish(b)


loop.run_until_complete(main())
