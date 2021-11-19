import time
from arclet.letoderea.entities.event import TemplateEvent
from arclet.letoderea.entities.subscriber import Subscriber
from arclet.letoderea.handler import argument_analysis, before_parser, param_parser

test_stack = [0]


class ExampleEvent(TemplateEvent):

    def get_params(self):
        return self.param_export(
            str='aa'
        )


def test(m: str):
    pass


test = Subscriber.set()(test)

e = ExampleEvent()
start = time.time()

for i in range(100000):

    param_parser(argument_analysis(test.callable_target), before_parser([], e.get_params))
    test_stack[0] += 1

print(round(test_stack[0] / (time.time() - start), 6), 'o/s')
