import time
import asyncio
from tarina import Empty
from arclet.letoderea.provider import Provider
from arclet.letoderea.handler import param_parser


loop = asyncio.new_event_loop()


class Test(Provider[str]):
    async def __call__(self, context: dict) -> str:
        return 'hello'


test = Test()


async def main():
    ctx = {'sr': 'world'}
    pros = [test]
    for _ in range(100000):
        await param_parser("sr", str, Empty, pros, ctx)

start = time.perf_counter_ns()
loop.run_until_complete(main())
print(round(100000 * 10e8 / (time.perf_counter_ns() - start), 6), 'o/s')
