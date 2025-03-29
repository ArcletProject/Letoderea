from __future__ import annotations

import pytest
from arclet.letoderea import Contexts, Provider, on
from arclet.letoderea.typing import generate_contexts


class IntProvider(Provider[int]):
    async def __call__(self, context: Contexts) -> int | None:
        return 123


class FloatProvider(Provider[float]):
    async def __call__(self, context: Contexts) -> float | None:
        return 1.23


class ProviderEvent:

    async def gather(self, context: Contexts):
        context["name"] = "Letoderea"

    class TestProvider(Provider[str]):
        async def __call__(self, context: Contexts) -> str | None:
            return context["name"]


class ProviderEvent1(ProviderEvent):

    async def gather(self, context: Contexts):
        await super().gather(context)
        context["is_true"] = True

    class Test1Provider(Provider[bool]):
        async def __call__(self, context: Contexts) -> bool | None:
            return context["is_true"]


@pytest.mark.asyncio
async def test_providers():

    @on(ProviderEvent1, providers=[IntProvider(), FloatProvider()])
    async def test_subscriber(
        name0: str,
        age0: int,
        is_true0: bool,
        num0: float,
        name1: str,
        age1: int,
        is_true1: bool,
        num1: float,
        name2: str,
        age2: int,
        is_true2: bool,
        num2: float,
        name3: str,
        age3: int,
        is_true3: bool,
        num3: float,
        name4: str,
        age4: int,
        is_true4: bool,
        num4: float,
        name5: str,
        age5: int,
        is_true5: bool,
        num5: float,
    ):
        assert name0 == name1 == name2 == name3 == name4 == name5 == "Letoderea"
        assert age0 == age1 == age2 == age3 == age4 == age5 == 123
        assert is_true0 is is_true1 is is_true2 is is_true3 is is_true4 is is_true5 is True
        assert num0 == num1 == num2 == num3 == num4 == num5 == 1.23

    ctx = await generate_contexts(ProviderEvent1())
    await test_subscriber.handle(ctx)

