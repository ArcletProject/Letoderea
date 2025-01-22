import asyncio
import gc
from datetime import datetime

from arclet.letoderea import Contexts, Propagator, es, propagate

test_stack = [0]


class TestTimeLimit(Propagator):
    def __init__(self, hour, minute):
        self.hour = hour
        self.minute = minute

    def check(self, ctx: Contexts):
        now = datetime.now()
        r = now >= datetime(year=now.year, month=now.month, day=now.day, hour=self.hour, minute=self.minute)
        ctx["_time_limit"] = r
        if r is False:
            return r

    def compose(self):
        yield self.check, True


class Interval(Propagator):
    def __init__(self, interval: float):
        self.success = True
        self.last_time = None
        self.interval = interval

    def before(self, _time_limit: bool):
        if not self.last_time:
            return
        self.success = (datetime.now() - self.last_time).total_seconds() > self.interval
        return self.success

    def after(self):
        if self.success:
            self.last_time = datetime.now()

    def compose(self):
        yield self.before, True
        yield self.after, False


class ExampleEvent:
    type: str = "ExampleEvent"
    msg: int = 0

    async def gather(self, context: dict):
        context["index"] = self.msg


@es.on(ExampleEvent)
@propagate(Interval(0.3), TestTimeLimit(0, 0))
async def test(
    index: int,
    a: str = "hello",
):
    gc.collect()
    print(index, a)


b = ExampleEvent()


async def main():
    for _ in range(11):
        await asyncio.sleep(0.2)
        b.msg += 1
        await es.publish(b)


asyncio.run(main())
