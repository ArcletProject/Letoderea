from arclet.letoderea import Publisher, EventSystem, provide, Contexts, BaseEvent
import asyncio


loop = asyncio.new_event_loop()
es = EventSystem(loop)


class TestEvent:
    def __init__(self, name: str):
        self.name = name

    async def gather(self, context: Contexts):
        context["name"] = self.name


class MyPublisher(Publisher):

    def validate(self, event: type[BaseEvent]):
        return event == TestEvent


test = provide(str, call="name")
my_publisher = MyPublisher("test")
es.add_publisher(my_publisher)
my_publisher.unsafe_push(TestEvent("hello world"))
my_publisher[TestEvent] += test()


@es.on(TestEvent)
async def test_subscriber(a: str):
    print(a)


loop.run_until_complete(asyncio.sleep(0.1))
