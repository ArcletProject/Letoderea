import asyncio
import gc
from datetime import datetime
from typing import Optional, Union

from arclet.letoderea import Interface, es
from arclet.letoderea.auxiliary import BaseAuxiliary

test_stack = [0]


class TestTimeLimit(BaseAuxiliary):
    def __init__(self, hour, minute):
        self.hour = hour
        self.minute = minute

    @property
    def id(self):
        return "TestTimeLimit"

    async def on_prepare(self, interface: Interface) -> Optional[bool]:
        now = datetime.now()
        return now >= datetime(year=now.year, month=now.month, day=now.day, hour=self.hour, minute=self.minute)


class Interval(BaseAuxiliary):
    def __init__(self, interval: float):
        self.success = True
        self.last_time = None
        self.interval = interval

    @property
    def before(self) -> set[str]:
        return {"TestTimeLimit"}

    @property
    def id(self):
        return "Interval"

    async def on_prepare(self, interface: Interface) -> Optional[Union[Interface.Update, bool]]:
        if not self.last_time:
            return True
        self.success = (datetime.now() - self.last_time).total_seconds() > self.interval
        return self.success

    async def on_cleanup(self, interface: Interface) -> Optional[bool]:
        if self.success:
            self.last_time = datetime.now()
            return True


class ExampleEvent:
    type: str = "ExampleEvent"
    msg: int = 0

    async def gather(self, context: dict):
        context["index"] = self.msg


@es.on(ExampleEvent, auxiliaries=[Interval(0.3), TestTimeLimit(0, 0)])
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
