from __future__ import annotations

import asyncio
import time
from pprint import pprint

from arclet.letoderea import Contexts, Provider, Publisher
from arclet.letoderea.handler import depend_handler


class IntProvider(Provider[int]):
    async def __call__(self, context: Contexts) -> int | None:
        return 123


class FloatProvider(Provider[float]):
    async def __call__(self, context: Contexts) -> float | None:
        return 1.23


class TestEvent:

    async def gather(self, context: Contexts):
        context["name"] = "Letoderea"

    class TestProvider(Provider[str]):
        async def __call__(self, context: Contexts) -> str | None:
            return context["name"]


class TestEvent1(TestEvent):

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["is_true"] = True

    class Test1Provider(Provider[bool]):
        async def __call__(self, context: Contexts) -> bool | None:
            return context["is_true"]


with Publisher("test", TestEvent1) as pub:

    @pub.register(providers=[IntProvider(), FloatProvider()])
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


pprint(test_subscriber.params)


async def main():
    ev = TestEvent1()
    s = time.perf_counter_ns()
    for _ in range(20000):
        await depend_handler(test_subscriber, ev)
    e = time.perf_counter_ns()
    n = e - s
    print(f"used {n/10e8}, {20000*10e8/n}o/s")
    print(f"{n / 20000} ns per loop with 20000 loops")


asyncio.run(main())
