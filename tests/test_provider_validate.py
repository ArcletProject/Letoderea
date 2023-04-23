from arclet.letoderea import provide, EventSystem
from typing import Union

es = EventSystem()


class TestEvent:
    type: str = "TestEvent"
    msg: int = 0

    async def gather(self, context: dict):
        context['index'] = self.msg


@es.on(TestEvent, providers=[provide(int, call=lambda x: x['index'])])
async def test(index: Union[str, int], a: str = "hello", ):
    print("test:", index, a)
    # test: 0 hello
    # provide, 'index' -> int -> index: Union[str, int]
    # no provide, a: str = "hello"


@es.on(TestEvent, providers=[provide(Union[int, str], call=lambda x: x['index'])])
async def test1(index: int, a: str = "hello", ):
    print("test1:", index, a)
    # test1: 0 0
    # provide, 'index' -> Union[int, str] -> index: int
    # provide, 'index' -> Union[int, str] -> a: str


es.loop.run_until_complete(es.publish(TestEvent()))