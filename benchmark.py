from __future__ import annotations

import asyncio
import pstats
import time
from cProfile import Profile
from pprint import pprint

from arclet.letoderea import Contexts, Param, Provider, on

loop = asyncio.new_event_loop()


class TestEvent:

    async def gather(self, context: Contexts): ...

    class TestProvider(Provider[str]):

        def validate(self, param: Param):
            return param.name == "a"

        async def __call__(self, context: Contexts) -> str | None:
            return "1"


@on(TestEvent)
async def sub(a):
    pass


a = TestEvent()
ctx: Contexts = {"$event": a}  # type: ignore
tasks = []
pprint(sub.params)
count = 20000


tasks.extend(loop.create_task(sub.handle(ctx.copy())) for _ in range(count))


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
        await sub.handle(ctx.copy())


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
        await sub.handle(ctx.copy())


prof = Profile()
prof.enable()
loop.run_until_complete(main2())
prof.disable()
prof.create_stats()

stats = pstats.Stats(prof)
stats.strip_dirs()
stats.sort_stats("tottime")
stats.print_stats(20)
