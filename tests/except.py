from __future__ import annotations

from arclet.letoderea import EventSystem, BaseEvent, provide, Contexts, bind, subscribe

es = EventSystem()


class TestEvent(BaseEvent):
    async def gather(self, context: Contexts):
        context["name"] = "Letoderea"


@subscribe(TestEvent)
@bind(provide(int, "age", 'a', _id="foo"))
@bind(provide(int, "age", 'b', _id="bar"))
@bind(provide(int, "age", 'c', _id="baz"))
async def test_subscriber(name: str, age: int):
    print(name, age)


es.loop.run_until_complete(es.publish(TestEvent()))
