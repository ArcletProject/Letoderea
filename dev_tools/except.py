from __future__ import annotations

from arclet.letoderea import EventSystem, BaseEvent, provider, Contexts, bind, register

es = EventSystem()


class TestEvent(BaseEvent):
    async def gather(self, context: Contexts):
        context["name"] = "Letoderea"


@register(TestEvent)
@bind(provider(int, lambda x: x.get('a')))
@bind(provider(int, lambda x: x.get('b')))
@bind(provider(int, lambda x: x.get('c')))
async def test_subscriber(name: str, age: int):
    print(name, age)


es.loop.run_until_complete(es.publish(TestEvent()))
