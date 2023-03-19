import asyncio
import time
from typing import List, Tuple, Any
from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent

loop = asyncio.new_event_loop()
test_stack = [0]
es = EventSystem(loop=loop)


class ExampleEvent(TemplateEvent):

    def get_params(self):
        return self.param_export(
            sr='aa'
        )


@es.register(ExampleEvent)
def test(sr):
    print(sr)


async def main():
    a = ExampleEvent()
    for i in range(10):
        await asyncio.sleep(0.1)
        es.event_publish(a)

start = time.time()
loop.run_until_complete(main())

#print(min(test_stack[0], 10000) / (time.time() - start), 'o/s')
