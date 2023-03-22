from typing import Optional

from arclet.letoderea import SupplyAuxiliary, SCOPE, Contexts, CombineMode
from arclet.letoderea.auxiliary import CombineExecutor
import asyncio


class Foo(SupplyAuxiliary):
    async def __call__(self, scope: SCOPE, context: Contexts) -> Optional[Contexts]:
        context['a'] = 1
        return context

    @property
    def available_scopes(self) -> set[SCOPE]:
        return {"prepare"}


class Bar(SupplyAuxiliary):
    async def __call__(self, scope: SCOPE, context: Contexts) -> Optional[Contexts]:
        if 'a' in context:
            context['b'] = context['a'] * 2
            return context

    @property
    def available_scopes(self) -> set[SCOPE]:
        return {"prepare"}


class Bar1(SupplyAuxiliary):
    async def __call__(self, scope: SCOPE, context: Contexts) -> Optional[Contexts]:
        context['b'] = 3
        return context

    @property
    def available_scopes(self) -> set[SCOPE]:
        return {"prepare"}


class Baz(SupplyAuxiliary):
    async def __call__(self, scope: SCOPE, context: Contexts) -> Optional[Contexts]:
        if 'a' in context:
            context['c'] = context['a'] - 5
            return context

    @property
    def available_scopes(self) -> set[SCOPE]:
        return {"prepare"}


class Qux(SupplyAuxiliary):
    async def __call__(self, scope: SCOPE, context: Contexts) -> Optional[Contexts]:
        if 'b' in context:
            context['d'] = context['b'] + 5
            return context

    @property
    def available_scopes(self) -> set[SCOPE]:
        return {"prepare"}


foo = Foo(CombineMode.AND)
bar = Bar(CombineMode.AND)
bar1 = Bar1(CombineMode.AND)
bar_1 = Bar(CombineMode.OR)
baz = Baz(CombineMode.OR)
qux = Qux(CombineMode.OR)


async def main():
    ctx = Contexts()
    exe1 = CombineExecutor([foo, bar])
    print(await exe1("prepare", ctx))
    ctx.clear()
    exe2 = CombineExecutor([foo, bar, baz, qux])
    print(await exe2("prepare", ctx))
    ctx.clear()
    exe3 = CombineExecutor([bar1, baz, qux])
    print(await exe3("prepare", ctx))
    ctx.clear()
    exe4 = CombineExecutor([bar_1, bar1, baz, qux])
    print(await exe4("prepare", ctx))
    ctx.clear()
    exe5 = CombineExecutor([foo, bar_1, bar1, baz, qux])
    print(await exe5("prepare", ctx))

asyncio.run(main())
