import asyncio
from arclet.letoderea import EventSystem, Depends, Contexts, Provider
from arclet.letoderea.provider import Param

es = EventSystem()


class ExampleEvent:
    async def gather(self, context: Contexts):
        context['data'] = 'b'

    class ExampleProvider(Provider[str]):

        def validate(self, param: Param):
            return param.name == 'a' and param.annotation == str

        async def __call__(self, context: Contexts):
            return context.get('a')


def wrapper(a: int):  # sourcery skip: raise-specific-error
    return int(a)


def wrapper1(a: int = Depends(wrapper)):  # sourcery skip: raise-specific-error
    return int(a)


@es.on(ExampleEvent, auxiliaries=[Depends(wrapper)])
async def handler(a: int = Depends(wrapper1)):
    print(a)


async def main():
    await es.publish(ExampleEvent())

asyncio.run(main())
