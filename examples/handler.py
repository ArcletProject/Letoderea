import asyncio
import time

from arclet.letoderea import Contexts, Provider, define
from arclet.letoderea.core import dispatch
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


async def exam(m: str): ...


sub = Subscriber(exam, providers=[ExampleEvent.TestProvider()])
pub = define(ExampleEvent)


@sub.propagate(prepend=True)
async def exam1(a: str):
    if a != "aa":
        return STOP


async def main():
    aa = ExampleEvent()
    ab = ExampleEvent("ab")
    subs = [(sub, pub.id) for _ in range(200)]
    for _ in range(200):
        await dispatch(aa, slots=subs)
        #await dispatch(ab, slots=subs)

s = time.perf_counter_ns()
loop.run_until_complete(main())
e = time.perf_counter_ns()
n = e - s

print(f"used {n/10e8}, {40000*10e8/n}o/s")
print(f"{n / 40000} ns per loop with 40000 loops")
