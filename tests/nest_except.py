import asyncio

from arclet.letoderea import Contexts, Depends, Provider, es
from arclet.letoderea.handler import ExceptionEvent
from arclet.letoderea.provider import Param


class ExampleEvent:
    async def gather(self, context: Contexts):
        context["data"] = "b"

    class ExampleProvider(Provider[str]):

        def validate(self, param: Param):
            return param.name == "a" and param.annotation == str

        async def __call__(self, context: Contexts):
            return context.get("a")


async def wrapper(data: str):  # sourcery skip: raise-specific-error
    return int(data)


async def wrapper1(a: int = Depends(wrapper)):  # sourcery skip: raise-specific-error
    return int(a)


async def handler(a: int = Depends(wrapper1)):
    print(a)


@es.on(ExceptionEvent)
async def exception_handler(event: ExceptionEvent):
    print(repr(event))

es.on(ExampleEvent, handler)


async def main():
    await es.publish(ExampleEvent())


asyncio.run(main())
