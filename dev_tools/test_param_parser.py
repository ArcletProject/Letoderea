import time
import asyncio
from arclet.letoderea.entities.event import TemplateEvent
from arclet.letoderea.entities.subscriber import Subscriber
from arclet.letoderea.handler import param_parser

loop = asyncio.new_event_loop()


class ExampleEvent(TemplateEvent):

    def get_params(self):
        return self.param_export(
            msg='aa'
        )


def test(sr:str):
    pass


test = Subscriber(test)

e = ExampleEvent()
revise = {}


async def main():
    for i in range(100000):
        await param_parser(test.params, e.get_params(), revise)

start = time.time()
loop.run_until_complete(main())
print(round(1000000 / (time.time() - start), 6), 'o/s')
print(revise)