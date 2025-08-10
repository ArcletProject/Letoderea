import pytest
import arclet.letoderea as le


@le.make_event
class ScopeEvent:
    foo: str


@pytest.mark.asyncio
async def test_event_dispatch():
    scope1 = le.Scope.of("scope1")
    scope2 = le.Scope.of("scope2")
    executed = []

    with scope1.context():
        @le.on(ScopeEvent)
        async def _1(foo: str):
            executed.append(1)

    with scope2.context():
        @le.on(ScopeEvent)
        async def _2(foo: str):
            executed.append(2)

    await le.publish(ScopeEvent("f"), scope=scope1)
    await le.post(ScopeEvent("f"), scope=scope1)
    assert executed == [1, 1]
    executed.clear()

    await le.publish(ScopeEvent("f"), scope="scope2")
    await le.post(ScopeEvent("f"), scope="scope2")
    assert executed == [2, 2]
    executed.clear()

    scope2.disable()
    await le.publish(ScopeEvent("f"), scope="scope2")
    assert executed == [1]
    executed.clear()

    scope2.enable()
    await le.publish(ScopeEvent("f"), scope="scope2")
    assert executed == [2]
