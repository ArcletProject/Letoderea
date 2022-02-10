import time
import asyncio
from arclet.letoderea.entities.event import TemplateEvent
from arclet.letoderea.entities.subscriber import Subscriber
from arclet.letoderea.handler import argument_analysis, before_parser, param_parser

test_stack = [0]

loop = asyncio.new_event_loop()


class ExampleEvent(TemplateEvent):

    def get_params(self):
        return self.param_export(
            str='aa'
        )


def test(m: str):
    pass


test = Subscriber.set()(test)

e = ExampleEvent()


async def main():
    for i in range(100000):
        await param_parser(test.params, e.get_params()[1])
        test_stack[0] += 1

start = time.time()
loop.run_until_complete(main())
print(round(test_stack[0] / (time.time() - start), 6), 'o/s')
