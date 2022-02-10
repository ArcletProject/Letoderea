import asyncio
import time

from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent

loop = asyncio.get_event_loop()
test_stack = [0]
es = EventSystem(loop=loop)


class ExampleEvent(TemplateEvent):

    def get_params(self):
        return self.param_export(
            str='aa'
        )


@es.register(ExampleEvent)
def test(m: str):
    test_stack[0] += 1


async def main():
    a = ExampleEvent()
    for i in range(10000):
        await asyncio.sleep(0.0)
        es.event_spread(a)

start = time.time()
loop.run_until_complete(main())

print(min(test_stack[0], 10000) / (time.time() - start), 'o/s')
