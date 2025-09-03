import pytest
import asyncio
from dataclasses import dataclass
import arclet.letoderea as le


@dataclass
class FetchEvent:
    foo: str
    bar: str


pub = le.define(FetchEvent, name="fetch_event")


@pytest.mark.asyncio
async def test_event_dispatch():
    from arclet.letoderea.core import setup_fetch

    await pub.push(FetchEvent("f1", "b1"))
    await pub.push(FetchEvent("f2", "b2"))

    setup_fetch()
    executed = []

    @le.on(FetchEvent)
    async def _1(
        foo,
        bar,
    ):
        assert foo.startswith("f")
        assert bar.startswith("b")
        executed.append(1)

    await asyncio.sleep(0.5)
    assert len(executed) == 2
