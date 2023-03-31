from __future__ import annotations

import asyncio
import pstats
import time
from arclet.letoderea import EventSystem, Provider, Contexts, Param
from arclet.letoderea.handler import depend_handler
from pprint import pprint
from cProfile import Profile
es = EventSystem()


class TestEvent:

    async def gather(self, context: Contexts):
        ...

    class TestProvider(Provider[str]):

        def validate(self, param: Param):
            return param.name == "a"

        async def __call__(self, context: Contexts) -> str | None:
            return "1"


@es.register(TestEvent)
async def test_subscriber(a):
    pass

a = TestEvent()
tasks = []
pprint(test_subscriber.params)
count = 20000


tasks.extend(
    es.loop.create_task(depend_handler(test_subscriber, a))
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
    es.loop.create_task(depend_handler(test_subscriber, a))
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

