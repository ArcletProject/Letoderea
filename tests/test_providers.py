from __future__ import annotations

import pytest
from arclet.letoderea import Contexts, Provider, ProviderFactory, on, Param
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


class MyFactory(ProviderFactory):

    def validate(self, param: Param) -> Provider | None:
        if param.name.startswith("age"):
            return IntProvider()
        if param.name.startswith("num"):
            return FloatProvider()


@pytest.mark.asyncio
async def test_providers():

    @on(ProviderEvent1, providers=[IntProvider(), FloatProvider()])
    async def s0(
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
    await s0.handle(ctx)


@pytest.mark.asyncio
async def test_providers_factory():

    @on(ProviderEvent, providers=[MyFactory])
    async def s1(
        name0: str,
        age0: int,
        num0: float,
        name1: str,
        age1: int,
        num1: float,
    ):
        assert name0 == name1 == "Letoderea"
        assert age0 == age1 == 123
        assert num0 == num1 == 1.23

    ctx = await generate_contexts(ProviderEvent())
    await s1.handle(ctx)
