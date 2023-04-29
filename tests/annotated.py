from arclet.letoderea import provide, EventSystem
from typing import TypeVar, Generic, TYPE_CHECKING
from typing_extensions import Annotated

es = EventSystem()
T = TypeVar("T")


class TestEvent:
    type: str = "TestEvent"
    index: int = 0

    async def gather(self, context: dict):
        context['index'] = self.index


class Deref(Generic[T]):
    def __init__(self, proxy_type: type[T]):
        self.proxy_type = proxy_type

    def __getattr__(self, item):
        if item not in self.proxy_type.__annotations__:
            raise AttributeError(f"{self.proxy_type.__name__} has no attribute {item}")
        return lambda x: x.get(item)


if TYPE_CHECKING:
    def deref(proxy_type: type[T]) -> T:
        ...
else:
    def deref(proxy_type: type[T]):
        return Deref(proxy_type)


@es.on(TestEvent)
async def test(
    index: Annotated[int, "index"],
    a: str = "hello"
):
    print("test:", index, a)


@es.on(TestEvent)
async def test1(
    index: Annotated[int, lambda x: x['index']],
    a: str = "hello"
):
    print("test:", index, a)


@es.on(TestEvent)
async def test1(
    index: Annotated[int, deref(TestEvent).index],
    a: str = "hello"
):
    print("test:", index, a)


es.loop.run_until_complete(es.publish(TestEvent()))
