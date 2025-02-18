import asyncio
import time

from arclet.letoderea import Contexts, Provider
from arclet.letoderea.handler import dispatch
from arclet.letoderea.subscriber import Subscriber, STOP

loop = asyncio.new_event_loop()


class ExampleEvent:
    def __init__(self, a: str = "aa"):
        self.a = a

    async def gather(self, context: Contexts):
        context["a"] = self.a

    class TestProvider(Provider[str]):
        async def __call__(self, context: Contexts) -> str:
            return context["a"]


async def test(m: str): ...


sub = Subscriber(test, providers=[ExampleEvent.TestProvider()])


@sub.propagate(prepend=True)
async def test1(a: str):
    if a != "aa":
        return STOP


async def main():
    aa = ExampleEvent()
    ab = ExampleEvent("ab")
    subs = [sub for _ in range(100)]
    for _ in range(500):
        await dispatch(subs, aa)
        await dispatch(subs, ab)

s = time.perf_counter_ns()
loop.run_until_complete(main())
e = time.perf_counter_ns()
n = e - s

print(f"used {n/10e8}, {50000*10e8/n}o/s")
print(f"{n / 50000} ns per loop with 50000 loops")
