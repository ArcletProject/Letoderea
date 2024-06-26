import asyncio
import time

from tarina import Empty

from arclet.letoderea.provider import Provider
from arclet.letoderea.subscriber import CompileParam

loop = asyncio.new_event_loop()


class Test(Provider[str]):
    async def __call__(self, context: dict) -> str:
        return "hello"


test = Test()


async def main():
    param = CompileParam("sr", str, Empty, [test], None, None)
    ctx = {"sr": "world"}
    for _ in range(100000):
        await param.solve(ctx)


start = time.perf_counter_ns()
loop.run_until_complete(main())
end = time.perf_counter_ns()
print(round(100000 * 10e8 / (end - start), 6), "o/s")
