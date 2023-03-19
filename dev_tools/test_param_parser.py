import time
import asyncio
from arclet.letoderea.provider import Provider
from arclet.letoderea.subscriber import Subscriber
from arclet.letoderea.handler import param_parser

loop = asyncio.new_event_loop()


def test(sr: str):
    pass


class Test(Provider[str]):
    async def __call__(self, context: dict) -> str:
        return 'hello'


test = Subscriber(test, providers=[Test()])

revise = {}


async def main():
    for _ in range(100000):
        await param_parser(test.params, {'sr': 'world'}, revise)

start = time.perf_counter_ns()
loop.run_until_complete(main())
print(round(100000 * 10e8 / (time.perf_counter_ns() - start), 6), 'o/s')
print(revise)
