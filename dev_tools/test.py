import asyncio
import time
from typing import Union
import gc
from arclet.letoderea.handler import await_exec_target
from arclet.letoderea import EventSystem
from arclet.letoderea.utils import gather_inserts
from arclet.letoderea.entities.subscriber import Subscriber
from arclet.letoderea.entities.event import TemplateEvent

loop = asyncio.get_event_loop()
es = EventSystem(loop=loop)


class ExampleEvent(TemplateEvent):

    def get_params(self):
        return self.param_export(
            abc='1'
        )


@es.register(ExampleEvent)
async def test(m=123):
    a = m + 1

a = ExampleEvent()
tasks = []

count = 20000
inserts = gather_inserts(a)
for _ in range(count):
    tasks.append(await_exec_target(test, inserts.copy()))

s = time.time()
loop.run_until_complete(asyncio.gather(*tasks))
e = time.time()
n = e - s
print(f"used {n}, {count/n}o/s")
print(test.revise_dispatches)
print(gc.collect())
