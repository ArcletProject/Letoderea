import asyncio

import pytest

from arclet.letoderea import deref, enter_if, on, es, defer
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
        else:  # pragma: no cover
            print("[subscriber] >>> no result received, continue waiting")
            return
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
        end = await s.wait(default=5678, timeout=0.2)
        executed.append(end - start)

    a = ExampleEvent()
    a.msg = "hello"
    b = ExampleEvent()
    b.msg = "world"

    es.publish(a)
    await asyncio.sleep(0.1)
    es.publish(b)
    await asyncio.sleep(0.1)
    assert executed == [1, 2, 123]

    executed.clear()
    await es.publish(a)
    assert executed == [1, 4567]

    res = await es.post(b)
    assert res
    assert res.value == 1234

    s.dispose()

    with pytest.raises(RuntimeError):
        await s_1.handle(await generate_contexts(a))


@pytest.mark.asyncio
async def test_breakpoint_dispose():

    executed = []

    async def handler(msg: str):
        return msg

    @on(ExampleEvent)
    @enter_if(deref(ExampleEvent).msg.startswith("/start"))
    async def s(msg: str):
        executed.append(1)
        if msg == "/start":
            step = step_out(ExampleEvent, handler, priority=18, block=True)
            defer(step.dispose)
            res = await step.wait()
            executed.append(res)
        else:
            executed.append(msg[7:])
        return

    a = ExampleEvent()
    a.msg = "/start"
    b = ExampleEvent()
    b.msg = "1234"
    c = ExampleEvent()
    c.msg = "/start 1234"

    es.publish(a)
    await asyncio.sleep(0.1)
    es.publish(b)
    await asyncio.sleep(0.1)
    assert executed == [1, '1234']

    executed.clear()

    es.publish(a)
    await asyncio.sleep(0.1)
    es.publish(c)
    await asyncio.sleep(0.1)
    assert executed == [1, 1, '1234']

    executed.clear()

    es.publish(a)
    await asyncio.sleep(0.1)
    es.publish(b)
    await asyncio.sleep(0.1)
    es.publish(c)
    await asyncio.sleep(0.1)

    assert executed == [1, '1234', 1, '1234']
