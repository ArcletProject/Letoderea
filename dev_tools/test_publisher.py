from arclet.letoderea import Publisher, EventSystem, provider, Contexts, bind
import asyncio


loop = asyncio.new_event_loop()
es = EventSystem(loop)


class TestEvent:
    def __init__(self, name: str):
        self.name = name

    async def gather(self, context: Contexts):
        context["name"] = self.name


test = provider(str, call=lambda x: x.get("name"))
my_publisher = Publisher("test", TestEvent)
my_publisher.unsafe_push(TestEvent("hello world"))
my_publisher[TestEvent] += test()


@es.register(TestEvent)
async def test_subscriber(a: str):
    print(a)


loop.run_until_complete(asyncio.sleep(0.1))
