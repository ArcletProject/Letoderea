import asyncio

from arclet.letoderea import EventSystem
from arclet.letoderea.builtin.breakpoint import Breakpoint, StepOut
from arclet.letoderea.typing import Contexts

es = EventSystem()
break_point = Breakpoint(es)


async def handler(msg: str):
    if msg == "continue!":
        print("[breakpoint] <<< receive in handler:", f'"{msg}"')
        return "world!"


class ExampleEvent:
    msg: str

    async def gather(self, context: Contexts):
        context["msg"] = self.msg


@es.on(ExampleEvent)
async def test(msg: str):
    if msg == "hello":
        print('[subscriber] >>> wait for msg: "continue!" ')
        out = StepOut([ExampleEvent], handler)
        print("[subscriber] >>> current out:", out)
        with break_point:
            res = await out.wait(default="default")
        print("[subscriber] >>> wait result:", f'"{res}"')
        print("[subscriber] >>> finish!")


a = ExampleEvent()
a.msg = "hello"
b = ExampleEvent()
b.msg = "continue!"
c = ExampleEvent()
c.msg = "wait"


async def main():
    for i in range(6):
        if i % 3 == 0:
            print(i + 1, 'event posted with msg: "hello"')
            es.publish(a)
        elif (i - 1) % 3 == 0:
            print(i + 1, 'event posted with msg: "wait"')
            es.publish(c)
        else:
            print(i + 1, 'event posted with msg: "continue!"')
            es.publish(b)
        await asyncio.sleep(1)


asyncio.run(main())
