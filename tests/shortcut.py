from arclet.letoderea import bypass_if, EventSystem
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


def equal(x, y):
    return lambda ctx: x(ctx) == y


def not_equal(x, y):
    return lambda ctx: x(ctx) != y


@es.on(TestEvent)
@bypass_if(lambda x: x['index'] == 0)
async def test(
    index: Annotated[int, "index"],
    a: str = "hello"
):
    print("enter when index != 0")
    print("test1:", index, a)


@es.on(TestEvent)
@bypass_if(not_equal(deref(TestEvent).index, 0))
async def test1(
    index: Annotated[int, lambda x: x['index']],
    a: str = "hello"
):
    print("enter when index == 0")
    print("test2:", index, a)


async def main():
    e1 = TestEvent()
    e1.index = 0
    await es.publish(e1)
    e2 = TestEvent()
    e2.index = 1
    await es.publish(e2)


es.loop.run_until_complete(main())
