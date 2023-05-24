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
my_publisher[TestEvent] += test()


@es.on(TestEvent, publisher=my_publisher)
async def test_subscriber(a: str):
    print(a)


async def main():
    await my_publisher.publish(TestEvent("hello world"))


loop.run_until_complete(main())
