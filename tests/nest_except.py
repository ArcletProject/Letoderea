import asyncio

from arclet.letoderea import Contexts, Depends, es, Provider
from arclet.letoderea.provider import Param


class ExampleEvent:
    async def gather(self, context: Contexts):
        context["data"] = "b"

    class ExampleProvider(Provider[str]):

        def validate(self, param: Param):
            return param.name == "a" and param.annotation == str

        async def __call__(self, context: Contexts):
            return context.get("a")


async def wrapper(a: str):  # sourcery skip: raise-specific-error
    return int(a)


async def wrapper1(a: int = Depends(wrapper)):  # sourcery skip: raise-specific-error
    return int(a)


async def handler(a: int = Depends(wrapper1)):
    print(a)


es.on(ExampleEvent, handler)


async def main():
    await es.publish(ExampleEvent())


asyncio.run(main())
