import pytest
from typing import Literal, Any
import arclet.letoderea as le


@le.make_event
class OverloadEvent:
    a: Any = None
    b: Any = None
    c: Any = None

    def check_result(self, value) -> le.Result[int] | None:  # pragma: no cover
        if isinstance(value, int):
            return le.Result(value)

class OverloadBaseEvent:
    msg: str


class FooEvent(OverloadBaseEvent):
    msg = "foo"


class BarEvent(OverloadBaseEvent):
    msg = "bar"



@pytest.mark.asyncio
async def test_overload():
    executed = []

    @le.overload
    async def s() -> Literal[0]:
        executed.append((0, None))
        return 0

    @le.overload
    async def s(a: int, b: Literal[True]) -> Literal[1]:
        executed.append((1, a))
        return 1

    @le.overload
    async def s(a: int, b: Literal[False]) -> Literal[2]:
        executed.append((2, b))
        return 2

    @le.overload
    async def s(a: int, *, c: int) -> Literal[3]:
        executed.append((3, c * a))
        return 3

    @le.on(OverloadEvent)
    @le.apply_overload
    async def s(a: int | None = None, b: bool | None = None, c: int | None = None) -> int:
        ...

    assert await le.call_overload(s) == 0
    assert await le.call_overload(s, 10, True) == 1
    assert await le.call_overload(s, 20, False) == 2
    assert await le.call_overload(s, 5, c=4) == 3

    assert executed == [(0, None), (1, 10), (2, False), (3, 20)]

    executed.clear()

    res1 = await le.post(OverloadEvent())
    assert res1 and res1.value == 0
    res2 = await le.post(OverloadEvent(a=10, b=True))
    assert res2 and res2.value == 1
    res3 = await le.post(OverloadEvent(a=20, b=False))
    assert res3 and res3.value == 2
    res4 = await le.post(OverloadEvent(a=5, c=4))
    assert res4 and res4.value == 3


@pytest.mark.asyncio
async def test_event_dispatch():
    executed = []

    @le.overload
    async def handle(event: FooEvent):
        executed.append("foo")
        return "foo"

    @le.overload
    async def handle(event: BarEvent):
        executed.append("bar")
        return "bar"

    @le.on(OverloadBaseEvent)
    @le.apply_overload
    async def handle(event: OverloadBaseEvent):
        ...

    res1 = await le.post(FooEvent())
    assert res1 and res1.value == "foo"
    res2 = await le.post(BarEvent())
    assert res2 and res2.value == "bar"

    assert executed == ["foo", "bar"]


@pytest.mark.asyncio
async def test_overload_failed():
    with pytest.raises(TypeError, match="No overloads found for the function."):
        @le.on(OverloadEvent)
        @le.apply_overload
        async def f(a: int | str):
            ...

    with pytest.raises(TypeError, match="Implementation function must contain all parameters of overloads."):
        @le.overload
        async def f1(a: int) -> int:  # pragma: no cover
            return a

        @le.overload
        async def f1(a: str, b: bool) -> str:  # pragma: no cover
            return a

        @le.on(OverloadEvent)
        @le.apply_overload
        async def f1(a: int | str):
            ...

    with pytest.raises(le.UnresolvedRequirement):
        @le.overload
        async def f2(a: int) -> int:  # pragma: no cover
            return a

        @le.overload
        async def f2(a: str, b: bool) -> str:  # pragma: no cover
            return a

        @le.on(OverloadEvent)
        @le.apply_overload
        async def f2(a: int | str, b: bool):
            ...

        await le.call_overload(f2, 10, "True")  # type: ignore


@pytest.mark.asyncio
async def test_overload_depend():
    executed = []

    async def dep1(b: bool):
        if isinstance(b, bool):
            return str(b)

    @le.overload
    async def s1(a: int) -> Literal[1]:
        executed.append((1, a))
        return 1

    @le.overload
    async def s1(a: int, d: str = le.Depends(dep1)) -> Literal[2]:
        executed.append((2, d))
        return 2

    @le.on(OverloadEvent)
    @le.apply_overload
    async def s1(a: int | None = None, d: str | None = None, e: float | None = None) -> int:
        ...

    res1 = await le.post(OverloadEvent(a=10))
    assert res1 and res1.value == 1
    res2 = await le.post(OverloadEvent(a=10, b=True))
    assert res2 and res2.value == 2
