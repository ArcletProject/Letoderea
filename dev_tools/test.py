from __future__ import annotations

import asyncio
import pstats
import time
from arclet.letoderea import EventSystem, BaseEvent, Provider, Collection, event_ctx
from arclet.letoderea.handler import depend_handler
from pprint import pprint
from cProfile import Profile
es = EventSystem()


class TestEvent(BaseEvent):
    def __init__(self, name: str):
        self.name = name

    async def gather(self, collection: Collection):
        collection["name"] = self.name

    class TestProvider(Provider[str]):
        async def __call__(self, collection: Collection) -> str | None:
            return collection.get("name")


@es.register(TestEvent)
async def test_subscriber(a: str):
    pass

a = TestEvent("1")
tasks = []
pprint(test_subscriber.params)
count = 20000


with event_ctx.use(a):
    tasks.extend(
        es.loop.create_task(depend_handler(test_subscriber, [a]))
        for _ in range(count)
    )


    async def main():
        await asyncio.gather(*tasks)

    s = time.perf_counter_ns()
    es.loop.run_until_complete(main())
    e = time.perf_counter_ns()
    n = e - s
    print(f"used {n/10e8}, {count*10e8/n}o/s")
    print(f"{n / count} ns per loop with {count} loops")

    tasks.clear()
    tasks.extend(
        es.loop.create_task(depend_handler(test_subscriber, [a]))
        for _ in range(count)
    )

    async def main():
        await asyncio.gather(*tasks)

    prof = Profile()
    prof.enable()
    es.loop.run_until_complete(main())
    prof.disable()
    prof.create_stats()

    stats = pstats.Stats(prof)
    stats.strip_dirs()
    stats.sort_stats('tottime')
    stats.print_stats(20)


