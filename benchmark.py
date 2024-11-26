from __future__ import annotations

import asyncio
import pstats
import time
from cProfile import Profile
from pprint import pprint

from arclet.letoderea import Contexts, es, Param, Provider
from arclet.letoderea.handler import depend_handler

loop = asyncio.new_event_loop()


class TestEvent:

    async def gather(self, context: Contexts): ...

    class TestProvider(Provider[str]):

        def validate(self, param: Param):
            return param.name == "a"

        async def __call__(self, context: Contexts) -> str | None:
            return "1"


@es.on(TestEvent)
async def test_subscriber(a):
    pass


a = TestEvent()
tasks = []
pprint(test_subscriber.params)
count = 20000


tasks.extend(loop.create_task(depend_handler(test_subscriber, a)) for _ in range(count))


async def main():
    await asyncio.gather(*tasks)


s = time.perf_counter_ns()
loop.run_until_complete(main())
e = time.perf_counter_ns()
n = e - s
print("RUN 1:")
print(f"used {n/10e8}, {count*10e8/n}o/s")
print(f"{n / count} ns per task with {count} tasks gather")


async def main1():
    for _ in range(count):
        await depend_handler(test_subscriber, a)


s = time.perf_counter_ns()
loop.run_until_complete(main1())
e = time.perf_counter_ns()
n = e - s
print("RUN 2:")
print(f"used {n/10e8}, {count*10e8/n}o/s")
print(f"{n / count} ns per loop with {count} loops")

# tasks.clear()
# tasks.extend(
#     es.loop.create_task(depend_handler(test_subscriber, a))
#     for _ in range(count)
# )


async def main2():
    for _ in range(count):
        await depend_handler(test_subscriber, a)


prof = Profile()
prof.enable()
loop.run_until_complete(main2())
prof.disable()
prof.create_stats()

stats = pstats.Stats(prof)
stats.strip_dirs()
stats.sort_stats("tottime")
stats.print_stats(20)
