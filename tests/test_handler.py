import asyncio
import time
from arclet.letoderea.handler import depend_handler
from arclet.letoderea.subscriber import Subscriber
from arclet.letoderea import Provider, Contexts

loop = asyncio.new_event_loop()


class ExampleEvent:
    async def gather(self, context: Contexts):
        context["a"] = "aa"

    class TestProvider(Provider[str]):
        async def __call__(self, context: Contexts) -> str:
            return context["a"]


async def test(m: str):
    ...


sub = Subscriber(test, providers=[ExampleEvent.TestProvider()])


async def main():
    a = ExampleEvent()
    for _ in range(50000):
        await depend_handler(sub, a)

s = time.perf_counter_ns()
loop.run_until_complete(main())
e = time.perf_counter_ns()
n = e - s

print(f"used {n/10e8}, {50000*10e8/n}o/s")
print(f"{n / 50000} ns per loop with 50000 loops")