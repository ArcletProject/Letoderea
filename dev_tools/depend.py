from arclet.letoderea.builtin.depend import Depend
from arclet.letoderea.handler import await_exec_target
import asyncio
from arclet.letoderea.entities.event import TemplateEvent
from arclet.letoderea.exceptions import ParsingStop

loop = asyncio.get_event_loop()


class ExampleEvent(TemplateEvent):

    def get_params(self):
        return self.param_export(
            str='a'
        )


def test_depend(m: str):
    if m == 'aa':
        return False
    raise ParsingStop


def test(m: bool = Depend(test_depend)):
    print(m)


async def main():
    try:
        a = ExampleEvent()
        await await_exec_target(test, [a])
    except ParsingStop:
        return

loop.run_until_complete(main())
