import asyncio
from arclet.letoderea import EventSystem, Depend, Contexts, Provider, ParsingStop
from arclet.letoderea.provider import T, Param

es = EventSystem()


class ExampleEvent:
    async def gather(self, ctx: Contexts):
        ctx['data'] = 'b'

    class ExampleProvider(Provider[str]):

        def validate(self, param: Param):
            return param.name == 'a' and param.annotation == str

        async def __call__(self, context: Contexts):
            return context.get('a')


def wrapper(a: int):  # sourcery skip: raise-specific-error
    return int(a)


def wrapper1(a: int = Depend(wrapper)):  # sourcery skip: raise-specific-error
    return int(a)


@es.on(ExampleEvent, auxiliaries=[Depend(wrapper)])
async def handler(a: int = Depend(wrapper1)):
    print(a)


async def main():
    await es.publish(ExampleEvent())

es.loop.run_until_complete(main())
