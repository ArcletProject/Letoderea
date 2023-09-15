import asyncio
from arclet.letoderea import EventSystem, auxilia, AuxType
from arclet.letoderea.typing import Contexts
from arclet.letoderea.builtin.breakpoint import StepOut, Breakpoint

event = asyncio.Event()
loop = asyncio.get_event_loop()
es = EventSystem(loop=loop)
break_point = Breakpoint(es)


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
        context['msg'] = self.msg


@es.on(ExampleEvent, auxiliaries=[auxilia(AuxType.judge, prepare=lambda x: x['msg'] == 'hello')])
async def test():
    if event.is_set():
        print("[subscriber] >>> program already running")
        return
    event.set()
    print("[subscriber] >>> wait for msg: \"continue!\" ")
    out = StepOut([ExampleEvent], handler)
    print("[subscriber] >>> current out:", out)
    async for res in out:
        if res is None:
            continue
        if res is False:
            break
        print("[subscriber] >>> wait result:", f'"{res}"')
        print("[subscriber] >>> finish!")
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
            print(i+1, 'event posted with msg: "hello"')
            es.publish(a)
        elif (i - 1) % 3 == 0:
            print(i+1, 'event posted with msg: "wait"')
            es.publish(c)
        else:
            print(i+1, 'event posted with msg: "continue!"')
            es.publish(b)
        await asyncio.sleep(1)
    es.publish(d)
    await asyncio.sleep(1)


loop.run_until_complete(main())
