import pytest

import arclet.letoderea as le


@le.make_event
class ScopeEvent:
    foo: str


@pytest.mark.asyncio
async def test_scope_context_manager():
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
    assert executed == []
    executed.clear()

    scope2.enable()
    await le.publish(ScopeEvent("f"), scope="scope2")
    assert executed == [2]


@pytest.mark.no_scope
@pytest.mark.asyncio
async def test_scope_nest():
    executed = []
    scope1 = le.Scope.of("scope1")

    with scope1.context():
        with scope1.context():
            @le.on(ScopeEvent)
            async def _1(foo: str):
                executed.append(1)

            scope2 = le.Scope.of("scope2")
            with scope2.context():
                @le.on(ScopeEvent)
                async def _2(foo: str):
                    executed.append(2)

            scope3 = le.Scope.of("scope3")
            with scope3.context():
                @le.on(ScopeEvent)
                async def _3(foo: str):
                    executed.append(3)

    await le.publish(ScopeEvent("f"), scope=scope1)
    await le.post(ScopeEvent("f"), scope=scope1)
    assert executed == [1, 1]
    executed.clear()

    await le.publish(ScopeEvent("f"), scope=scope2)
    await le.post(ScopeEvent("f"), scope=scope2)
    assert executed == [2, 2]
    executed.clear()

    scope2.disable()
    await le.publish(ScopeEvent("f"))
    assert executed == [1, 3]

    executed.clear()
    scope2.enable()
    scope1.disable()
    await le.publish(ScopeEvent("f"))
    assert executed == []

    scope1.enable()
    await le.publish(ScopeEvent("f"))
    assert executed == [1, 2, 3]

    scope3.dispose()
    assert len(scope1._subscopes) == 1

    executed.clear()
    await le.publish(ScopeEvent("f"))
    assert executed == [1, 2]

    scope1.dispose()
    await scope1.cleanup()
