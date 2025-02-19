import asyncio

import pytest

from arclet.letoderea import deref, enter_if, es
from arclet.letoderea.breakpoint import StepOut
from arclet.letoderea.typing import Contexts

event = asyncio.Event()


class ExampleEvent:
    msg: str

    async def gather(self, context: Contexts):
        context["msg"] = self.msg


@pytest.mark.asyncio
async def test_breakpoint():
    executed = []

    async def handler(msg: str):
        if msg == "continue!":
            print("[breakpoint] <<< receive in handler:", f'"{msg}"')
            executed.append(1)
            return "world!"
        if msg == "end.":
            print("[breakpoint] <<< receive terminal signal")
            executed.append(3)
            return False
        print("[breakpoint] <<< receive event:", msg)
        executed.append(2)

    @es.on(ExampleEvent)
    @enter_if(deref(ExampleEvent).msg == "hello")
    async def s():
        if event.is_set():
            print("[subscriber] >>> program already running")
            return
        event.set()
        executed.append(0)
        print('[subscriber] >>> wait for msg: "continue!" ')
        out = StepOut([ExampleEvent], handler)
        async for res in out(default=False):
            executed.append(4)
            if res is False:
                print("[subscriber] >>> finish!")
                break
            print("[subscriber] >>> wait result:", f'"{res}"')
        executed.append(5)
        event.clear()

    a = ExampleEvent()
    a.msg = "hello"
    b = ExampleEvent()
    b.msg = "continue!"
    c = ExampleEvent()
    c.msg = "wait"
    d = ExampleEvent()
    d.msg = "end."

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
        await asyncio.sleep(0.1)
    print(7, 'event posted with msg: "end."')
    await es.publish(d)
    assert executed == [0, 2, 1, 4, 2, 2, 1, 4, 3, 4, 5]