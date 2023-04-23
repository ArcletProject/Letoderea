from __future__ import annotations

import asyncio
import time
from pprint import pprint
from arclet.letoderea import EventSystem, BaseEvent, Provider, Contexts, bind
from arclet.letoderea.handler import depend_handler

es = EventSystem()


class IntProvider(Provider[int]):
    async def __call__(self, context: Contexts) -> int | None:
        return 123


class BoolProvider(Provider[bool]):
    async def __call__(self, context: Contexts) -> bool | None:
        return True


class FloatProvider(Provider[float]):
    async def __call__(self, context: Contexts) -> float | None:
        return 1.23


class TestEvent(BaseEvent):

    async def gather(self, context: Contexts):
        context["name"] = "Letoderea"

    class TestProvider(Provider[str]):
        async def __call__(self, context: Contexts) -> str | None:
            return context['name']


@es.on(TestEvent)
@bind(IntProvider, BoolProvider, FloatProvider)
async def test_subscriber(
    name0: str,
    age0: int,
    is_true0: bool,
    num0: float,
    name1: str,
    age1: int,
    is_true1: bool,
    num1: float,
    name2: str,
    age2: int,
    is_true2: bool,
    num2: float,
    name3: str,
    age3: int,
    is_true3: bool,
    num3: float,
    name4: str,
    age4: int,
    is_true4: bool,
    num4: float,
    name5: str,
    age5: int,
    is_true5: bool,
    num5: float,
):
    # print(name, age, is_true, num, name1)
    ...

tasks = [
    es.loop.create_task(depend_handler(test_subscriber, TestEvent()))
    for _ in range(20000)
]

pprint(test_subscriber.params)


async def main():
    await asyncio.gather(*tasks)

s = time.perf_counter_ns()
es.loop.run_until_complete(main())
e = time.perf_counter_ns()
n = e - s
print(f"used {n/10e8}, {20000*10e8/n}o/s")
print(f"{n / 20000} ns per loop with 20000 loops")
