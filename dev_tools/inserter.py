import asyncio
from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent, Insertable

loop = asyncio.get_event_loop()
test_stack = [0]
es = EventSystem(loop=loop)


class TestInserter(Insertable):

    @classmethod
    def get_params(cls):
        return cls.param_export(
            str='hello'
        )


class ExampleEvent(TemplateEvent):
    type: str = "ExampleEvent"
    msg: int

    def get_params(self):
        return self.param_export(
            TestInserter,
            ExampleEvent=self,
            int=self.msg
        )


@es.register(ExampleEvent)
async def test(m: int, a: str, e: ExampleEvent):
    for i in range(5):
        await asyncio.sleep(0.1)
        print(m, a, e)
    loop.stop()


a = ExampleEvent()
a.msg = 1
es.event_spread(a)
loop.run_forever()
