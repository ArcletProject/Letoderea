import asyncio
import time

from arclet.letoderea.entities.delegate import EventDelegate
from arclet.letoderea.entities.subscriber import Subscriber
from arclet.letoderea.entities.event import TemplateEvent

loop = asyncio.get_event_loop()
test_stack = [0]


class ExampleEvent(TemplateEvent):

    def get_params(self):
        return self.param_export(
            str='aa'
        )


def test(m: str):
    test_stack[0] += 1


delegate = EventDelegate(event=ExampleEvent)
delegate += Subscriber.set()(test)


async def main():
    a = ExampleEvent()
    for i in range(10000):
        await delegate.executor(a)

start = time.time()
loop.run_until_complete(main())

print(min(test_stack[0], 10000) / (time.time() - start), 'o/s')
