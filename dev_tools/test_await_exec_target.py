import asyncio
import time
from arclet.letoderea.entities.event import TemplateEvent
from arclet.letoderea.handler import await_exec_target
from arclet.letoderea.entities.subscriber import Subscriber

loop = asyncio.get_event_loop()
test_stack = [0]


class ExampleEvent(TemplateEvent):

    def get_params(self):
        return self.param_export(
            str='aa'
        )


@Subscriber
def test():
    test_stack[0] += 1


async def main():
    a = ExampleEvent()
    for i in range(100000):
        await await_exec_target(test, [a])


start = time.time()
loop.run_until_complete(main())

print(min(test_stack[0], 100000) / (time.time() - start), 'o/s')
