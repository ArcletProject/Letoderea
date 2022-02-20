import asyncio
from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent

loop = asyncio.get_event_loop()
test_stack = [0]
es = EventSystem(loop=loop)


class ExampleEvent(TemplateEvent):
    msg: int

    def get_params(self):
        return self.param_export(
            ExampleEvent=self,
            msg=self.msg
        )


@es.register(ExampleEvent, inline_arguments={"b": "hello"})
async def test(m: int, b: str, e: ExampleEvent):
    for i in range(5):
        await asyncio.sleep(0.1)
        print(m, b, e)
    loop.stop()


a = ExampleEvent()
a.msg = 1
es.event_publish(a)
loop.run_forever()
