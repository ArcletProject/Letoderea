import asyncio
import time
from arclet.letoderea.entities.event import TemplateEvent
from arclet.letoderea.handler import await_exec_target
from arclet.letoderea.entities.subscriber import Subscriber

loop = asyncio.new_event_loop()

class ExampleEvent(TemplateEvent):

    def get_params(self):
        return self.param_export(
            str='aa'
        )


@Subscriber
def test(m: str):
    ...


async def main():
    a = ExampleEvent()
    for i in range(100000):
        await await_exec_target(test, [a])


start = time.time()
loop.run_until_complete(main())

print(100000 / (time.time() - start), 'o/s')
