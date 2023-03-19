from __future__ import annotations

import asyncio
import time
from arclet.letoderea import EventSystem, BaseEvent, Provider, Collection, event_ctx
from arclet.letoderea.handler import depend_handler
es = EventSystem()


class TestEvent(BaseEvent):
    def __init__(self, name: str):
        self.name = name

    async def gather(self, collection: Collection):
        collection["name"] = self.name


with TestEvent:
    class TestProvider(Provider[str]):
        async def __call__(self, collection: Collection) -> str | None:
            return collection.get("name")


@es.register(TestEvent)
async def test_subscriber(a: str):
    pass

a = TestEvent("1")
tasks = []

count = 20000


with event_ctx.use(a):
    tasks.extend(
        es.loop.create_task(depend_handler(test_subscriber, [a]))
        for _ in range(count)
    )
    s = time.time()
    es.loop.run_until_complete(asyncio.gather(*tasks))
    e = time.time()
    n = e - s
    print(f"used {n}, {count/n}o/s")

