import asyncio
import gc
from datetime import datetime
from typing import Optional

from arclet.letoderea import es, Interface
from arclet.letoderea.auxiliary import JudgeAuxiliary, Scope

test_stack = [0]


class TestTimeLimit(JudgeAuxiliary):
    def __init__(self, hour, minute):
        self.hour = hour
        self.minute = minute
        super().__init__(priority=10)

    @property
    def id(self):
        return "TestTimeLimit"

    @property
    def scopes(self):
        return {Scope.prepare}

    async def __call__(self, _, interface: Interface) -> Optional[bool]:
        now = datetime.now()
        return now >= datetime(year=now.year, month=now.month, day=now.day, hour=self.hour, minute=self.minute)


class Interval(JudgeAuxiliary):
    def __init__(self, interval: float):
        self.success = True
        self.last_time = None
        self.interval = interval
        super().__init__(priority=20)

    @property
    def id(self):
        return "Interval"

    @property
    def scopes(self):
        return {Scope.prepare, Scope.cleanup}

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if scope == Scope.prepare:
            if not self.last_time:
                return True
            self.success = (datetime.now() - self.last_time).total_seconds() > self.interval
            return self.success
        if self.success:
            self.last_time = datetime.now()
            return True


class ExampleEvent:
    type: str = "ExampleEvent"
    msg: int = 0

    async def gather(self, context: dict):
        context["index"] = self.msg


@es.on(ExampleEvent, auxiliaries=[TestTimeLimit(0, 0), Interval(0.3)])
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
        await es.post(b)


asyncio.run(main())
