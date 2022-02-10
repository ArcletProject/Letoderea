from arclet.letoderea.depend import Depend
from arclet.letoderea.handler import await_exec_target
import asyncio
from arclet.letoderea.entities.event import TemplateEvent

loop = asyncio.get_event_loop()


class ExampleEvent(TemplateEvent):

    def get_params(self):
        return self.param_export(
            str='aa'
        )


def test_depend(m: str):
    if m == 'aa':
        return True


def test(m: bool = Depend(test_depend)):
    print(m)


async def main():
    a = ExampleEvent()
    await await_exec_target(test, a.get_params)

loop.run_until_complete(main())

