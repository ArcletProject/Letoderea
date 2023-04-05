from typing import Optional

from arclet.letoderea import SupplyAuxiliary, Scope, Contexts, And, Or
from arclet.letoderea.auxiliary import CombineExecutor, Prepare
import asyncio


class Foo(SupplyAuxiliary):
    async def __call__(self, scope: Scope, context: Contexts) -> Optional[Contexts]:
        context['a'] = 1
        return context

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


class Bar(SupplyAuxiliary):
    async def __call__(self, scope: Scope, context: Contexts) -> Optional[Contexts]:
        if 'a' in context:
            context['b'] = context['a'] * 2
            return context

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


class Bar1(SupplyAuxiliary):
    async def __call__(self, scope: Scope, context: Contexts) -> Optional[Contexts]:
        context['b'] = 3
        return context

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


class Baz(SupplyAuxiliary):
    async def __call__(self, scope: Scope, context: Contexts) -> Optional[Contexts]:
        if 'a' in context:
            context['c'] = context['a'] - 5
            return context

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


class Qux(SupplyAuxiliary):
    async def __call__(self, scope: Scope, context: Contexts) -> Optional[Contexts]:
        if 'b' in context:
            context['d'] = context['b'] + 5
            return context

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


foo = Foo(And)
bar = Bar(And)
bar1 = Bar1(And)
bar_1 = Bar(Or)
baz = Baz(Or)
qux = Qux(Or)


async def main():
    ctx = Contexts()
    exe1 = CombineExecutor([foo, bar])
    print(await exe1(Prepare, ctx))
    ctx.clear()
    exe2 = CombineExecutor([foo, bar, baz, qux])
    print(await exe2(Prepare, ctx))
    ctx.clear()
    exe3 = CombineExecutor([bar1, baz, qux])
    print(await exe3(Prepare, ctx))
    ctx.clear()
    exe4 = CombineExecutor([bar_1, bar1, baz, qux])
    print(await exe4(Prepare, ctx))
    ctx.clear()
    exe5 = CombineExecutor([foo, bar_1, bar1, baz, qux])
    print(await exe5(Prepare, ctx))

asyncio.run(main())
