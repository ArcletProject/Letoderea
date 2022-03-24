from datetime import datetime
from arclet.letoderea.entities.auxiliary import BaseAuxiliary
import asyncio
from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent


loop = asyncio.get_event_loop()
test_stack = [0]
es = EventSystem(loop=loop)


class TestTimeLimit(BaseAuxiliary):
    def __init__(self, hour, minute):
        self.hour = hour
        self.minute = minute
        super().__init__()

        @self.set_aux("before_parse", "judge")
        def judge(*args):
            now = datetime.now()
            return now >= datetime(year=now.year, month=now.month, day=now.day, hour=self.hour, minute=self.minute)


class Interval(BaseAuxiliary):
    def __init__(self, interval: float):
        self.success = True
        self.last_time = datetime.now()
        self.interval = interval
        super().__init__()

        @self.set_aux("before_parse", "judge")
        def judge(*args):
            self.success = (datetime.now() - self.last_time).total_seconds() > self.interval
            return self.success

        @self.set_aux("execution_complete", "judge")
        def judge(*args):
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


@es.register(ExampleEvent, auxiliaries=[TestTimeLimit(17, 0), Interval(0.2)])
async def test(int: int, a: str = "hello", ):
    print(int, a)


b = ExampleEvent()


async def main():
    await asyncio.sleep(2)
    for i in range(11):
        await asyncio.sleep(0.1)
        b.msg += 1
        es.event_publish(b)

loop.run_until_complete(main())
