import asyncio
from typing import Optional

from arclet.letoderea import And, Interface, Or, Scope, SupplyAuxiliary
from arclet.letoderea.auxiliary import CombineExecutor, Prepare


class Foo(SupplyAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[Interface.Update]:
        return interface.update(a=1)

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


class Bar(SupplyAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[Interface.Update]:
        if (a := interface.query(int, "a", force_return=True)) is not None:
            return interface.update(b=a * 2)

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


class Bar1(SupplyAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[Interface.Update]:
        return interface.update(b=3)

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


class Baz(SupplyAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[Interface.Update]:
        if (b := interface.query(int, "b", force_return=True)) is not None:
            return interface.update(c=b - 5)

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}


class Qux(SupplyAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[Interface.Update]:
        if (b := interface.query(int, "b", force_return=True)) is not None:
            return interface.update(d=b + 5)

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
    interface = Interface({}, [])  # type: ignore
    exe1 = CombineExecutor([foo, bar])
    print(await exe1(Prepare, interface))
    interface.clear()
    exe2 = CombineExecutor([foo, bar, baz, qux])
    print(await exe2(Prepare, interface))
    interface.clear()
    exe3 = CombineExecutor([bar1, baz, qux])
    print(await exe3(Prepare, interface))
    interface.clear()
    exe4 = CombineExecutor([bar_1, bar1, baz, qux])
    print(await exe4(Prepare, interface))
    interface.clear()
    exe5 = CombineExecutor([foo, bar_1, bar1, baz, qux])
    print(await exe5(Prepare, interface))


asyncio.run(main())
