import asyncio
import time
from arclet.letoderea.handler import await_exec_target
from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent

loop = asyncio.get_event_loop()
es = EventSystem(loop=loop)


class ExampleEvent(TemplateEvent):

    def get_params(self):
        return self.param_export(
            str='1'
        )


@es.register(ExampleEvent)
async def test(m: str):
    pass

a = ExampleEvent()
delegate = es.get_publisher(ExampleEvent)[0][a]
tasks = []

count = 40000
for _ in range(count):
    tasks.append(await_exec_target(test, a.get_params))

start = time.time()
try:
    loop.run_until_complete(asyncio.gather(*tasks))
except:
    pass
end = time.time()
n = end - start
print(f"used {n}, {count/n} o/s")
