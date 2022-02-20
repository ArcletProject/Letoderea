import asyncio
from arclet.letoderea import EventSystem
from arclet.letoderea.entities.event import TemplateEvent

loop = asyncio.get_event_loop()
test_stack = [0]
es = EventSystem(loop=loop)


class TestInsert(TemplateEvent):
    msg: str = "hello"

    @classmethod
    def get_params(cls):
        return cls.param_export(
            str=cls.msg,
        )


class ExampleEvent(TemplateEvent):
    inserts = [TestInsert]
    msg: int

    def get_params(self):
        return self.param_export(
            ExampleEvent=self,
            int=self.msg
        )


@es.register(ExampleEvent)
async def test(m: int, b: str, e: ExampleEvent):
    for i in range(5):
        await asyncio.sleep(0.1)
        print(m, b, e)
    loop.stop()


a = ExampleEvent()
a.msg = 1
es.event_publish(a)
loop.run_forever()
