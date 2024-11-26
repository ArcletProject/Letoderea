import asyncio

from arclet.letoderea import AuxType, es, auxilia
from arclet.letoderea.breakpoint import StepOut
from arclet.letoderea.typing import Contexts

event = asyncio.Event()


async def handler(msg: str):
    if msg == "continue!":
        print("[breakpoint] <<< receive in handler:", f'"{msg}"')
        return "world!"
    if msg == "end.":
        print("[breakpoint] <<< receive terminal signal")
        return False
    print("[breakpoint] <<< receive event:", msg)


class ExampleEvent:
    msg: str

    async def gather(self, context: Contexts):
        context["msg"] = self.msg


@es.on(ExampleEvent, auxiliaries=[auxilia("hello", AuxType.judge, prepare=lambda x: x.query(str, "msg") == "hello")])
async def test():
    if event.is_set():
        print("[subscriber] >>> program already running")
        return
    event.set()
    print('[subscriber] >>> wait for msg: "continue!" ')
    out = StepOut([ExampleEvent], handler)
    print("[subscriber] >>> current out:", out)
    async for res in out():
        if res is None:
            continue
        if res is False:
            print("[subscriber] >>> finish!")
            break
        print("[subscriber] >>> wait result:", f'"{res}"')
    event.clear()


a = ExampleEvent()
a.msg = "hello"
b = ExampleEvent()
b.msg = "continue!"
c = ExampleEvent()
c.msg = "wait"
d = ExampleEvent()
d.msg = "end."


async def main():
    for i in range(6):
        if i % 3 == 0:
            print(i + 1, 'event posted with msg: "hello"')
            es.post(a)
        elif (i - 1) % 3 == 0:
            print(i + 1, 'event posted with msg: "wait"')
            es.post(c)
        else:
            print(i + 1, 'event posted with msg: "continue!"')
            es.post(b)
        await asyncio.sleep(1)
    print(7, 'event posted with msg: "end."')
    es.post(d)
    await asyncio.sleep(1)


asyncio.run(main())
