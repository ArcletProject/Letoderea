import asyncio

import pytest

from arclet.letoderea import deref, enter_if, on, es
from arclet.letoderea.breakpoint import step_out
from arclet.letoderea.typing import Contexts, generate_contexts


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

    out = step_out(ExampleEvent, handler)

    @on(ExampleEvent)
    @enter_if(deref(ExampleEvent).msg == "hello")
    async def s():
        if out.waiting:
            print("[subscriber] >>> program already running")
            return
        executed.append(0)
        print('[subscriber] >>> wait for msg: "continue!" ')
        async for res in out(default=False):
            executed.append(4)
            if res is False:
                print("[subscriber] >>> finish!")
                break
            print("[subscriber] >>> wait result:", f'"{res}"')
        executed.append(5)

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


@pytest.mark.asyncio
async def test_breakpoint_with_subscriber():

    executed = []

    @step_out()
    @on(ExampleEvent)
    @enter_if(deref(ExampleEvent).msg == "world")
    async def s():
        executed.append(2)
        end = 1234
        return end

    @on(ExampleEvent)
    @enter_if(deref(ExampleEvent).msg == "hello")
    async def s_1():
        executed.append(1)
        start = 1111
        end = await s.wait(default=1234)
        assert end - start == 123
        executed.append(3)

    a = ExampleEvent()
    a.msg = "hello"
    b = ExampleEvent()
    b.msg = "world"

    es.publish(a)
    await asyncio.sleep(0.1)
    es.publish(b)
    await asyncio.sleep(0.1)
    assert executed == [1, 2, 3]

    res = await es.post(b)
    assert res
    assert res.value == 1234

    s.dispose()

    with pytest.raises(RuntimeError):
        await s_1.handle(await generate_contexts(a))
