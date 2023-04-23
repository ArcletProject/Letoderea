from __future__ import annotations

from arclet.letoderea import EventSystem, BaseEvent, provide, Contexts, bind, subscribe

es = EventSystem()


class TestEvent(BaseEvent):
    async def gather(self, context: Contexts):
        context["name"] = "Letoderea"


@subscribe(TestEvent)
@bind(provide(int, "foo", lambda x: x.get('a')))
@bind(provide(int, "bar", lambda x: x.get('b')))
@bind(provide(int, "baz", lambda x: x.get('c')))
async def test_subscriber(name: str, age: int):
    print(name, age)


es.loop.run_until_complete(es.publish(TestEvent()))
