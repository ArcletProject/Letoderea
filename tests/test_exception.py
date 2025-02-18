import pytest

from dataclasses import dataclass
import arclet.letoderea as le


@le.make_event
@dataclass
class TestEvent:
    foo: str


@pytest.mark.asyncio
async def test_get_exc():
    executed = []

    @le.on(TestEvent)
    async def s():
        executed.append(1)
        raise Exception("test")

    @le.on(le.ExceptionEvent)
    async def _(event: le.ExceptionEvent, origin, exc: Exception, subscriber):
        executed.append(1)
        assert event.origin.__class__ is origin.__class__ is TestEvent
        assert event.exception.__class__ is exc.__class__ is Exception
        assert subscriber == s
        executed.append(1)

    await le.publish(TestEvent("1"))

    assert len(executed) == 3
