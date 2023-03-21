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


def test(m: str):
    ...


sub = Subscriber(test, providers=[ExampleEvent.TestProvider()])


async def main():
    a = ExampleEvent()
    for _ in range(100000):
        await depend_handler(test, a)


start = time.time()
loop.run_until_complete(main())

print(100000 / (time.time() - start), "o/s")
