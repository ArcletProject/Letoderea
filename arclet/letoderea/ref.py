from collections.abc import Container, Awaitable
from typing import TYPE_CHECKING, Any, TypeVar, cast
from collections.abc import Callable

from .typing import Contexts, EVENT
from .subscriber import Depend, SUBSCRIBER

T = TypeVar("T")


class Deref:
    def __init__(self, proxy_type: type):
        self.__proxy_type = proxy_type
        self.__items: dict[str | None, tuple[bool, Callable[[Contexts, Any], Awaitable[Any]]] | None] = {}
        self.__last_key = None

    def __getattr__(self, item):
        self.__items[item] = None
        self.__last_key = item
        return self

    def _isinstance(self, item: type):
        async def _(c, x): return isinstance(x, item)
        self.__items[self.__last_key] = (True, _)
        return self

    def __call__(self, *args, **kwargs):
        async def _call(ctx: Contexts, x):
            ps = ctx[SUBSCRIBER].providers
            resolved_args = [
                await arg.fork(ps)(ctx) if isinstance(arg, Depend) else await generate(arg)(ctx) if isinstance(arg, Deref) else arg
                for arg in args
            ]
            resolved_kwargs = {
                k: await v.fork(ps)(ctx) if isinstance(v, Depend) else await generate(v)(ctx) if isinstance(v, Deref) else v
                for k, v in kwargs.items()
            }
            return x(*resolved_args, **resolved_kwargs)
        self.__items[self.__last_key] = (False, _call)
        return self

    def __bool__(self):
        async def _(c, x): return bool(x)
        self.__items[self.__last_key] = (True, _)
        return self

    def __eq__(self, other, *, _is: bool = False):  # type: ignore
        if isinstance(other, Deref):
            async def _(c, x): return (x is await generate(other)(c)) if _is else (x == await generate(other)(c))
            self.__items[self.__last_key] = (True, _)
        elif isinstance(other, Depend):
            async def _(c, x):
                ps = c[SUBSCRIBER].providers
                return (x is await other.fork(ps)(c)) if _is else (x == await other.fork(ps)(c))
            self.__items[self.__last_key] = (True, _)
        else:
            async def _(c, x): return (x is other) if _is else (x == other)
            self.__items[self.__last_key] = (True, _)
        return self

    def __ne__(self, other, *, _is: bool = False):  # type: ignore
        if isinstance(other, Deref):
            async def _(c, x): return (x is not await generate(other)(c)) if _is else (x != await generate(other)(c))
            self.__items[self.__last_key] = (True, _)
        elif isinstance(other, Depend):
            async def _(c, x):
                ps = c[SUBSCRIBER].providers
                return (x is not await other.fork(ps)(c)) if _is else (x != await other.fork(ps)(c))
            self.__items[self.__last_key] = (True, _)
        else:
            async def _(c, x): return (x is not other) if _is else (x != other)
            self.__items[self.__last_key] = (True, _)
        return self

    def __lt__(self, other):
        if isinstance(other, Deref):
            async def _(c, x): return x < await generate(other)(c)
            self.__items[self.__last_key] = (True, _)
        elif isinstance(other, Depend):
            async def _(c, x):
                ps = c[SUBSCRIBER].providers
                return x < await other.fork(ps)(c)
            self.__items[self.__last_key] = (True, _)
        else:
            async def _(c, x): return x < other
            self.__items[self.__last_key] = (True, _)
        return self

    def __gt__(self, other):
        if isinstance(other, Deref):
            async def _(c, x): return x > await generate(other)(c)
            self.__items[self.__last_key] = (True, _)
        elif isinstance(other, Depend):
            async def _(c, x):
                ps = c[SUBSCRIBER].providers
                return x > await other.fork(ps)(c)
            self.__items[self.__last_key] = (True, _)
        else:
            async def _(c, x): return x > other
            self.__items[self.__last_key] = (True, _)
        return self

    def __le__(self, other):
        if isinstance(other, Deref):
            async def _(c, x): return x <= await generate(other)(c)
            self.__items[self.__last_key] = (True, _)
        elif isinstance(other, Depend):
            async def _(c, x):
                ps = c[SUBSCRIBER].providers
                return x <= await other.fork(ps)(c)
            self.__items[self.__last_key] = (True, _)
        else:
            async def _(c, x): return x <= other
            self.__items[self.__last_key] = (True, _)
        return self

    def __ge__(self, other):
        if isinstance(other, Deref):
            async def _(c, x): return x >= await generate(other)(c)
            self.__items[self.__last_key] = (True, _)
        elif isinstance(other, Depend):
            async def _(c, x):
                ps = c[SUBSCRIBER].providers
                return x >= await other.fork(ps)(c)
            self.__items[self.__last_key] = (True, _)
        else:
            async def _(c, x): return x >= other
            self.__items[self.__last_key] = (True, _)
        return self

    def __contains__(self, item, *, _left: bool = False):
        if isinstance(item, Deref):
            async def _(c, x): return (x in await generate(item)(c)) if _left else (await generate(item)(c) in x)
            self.__items[self.__last_key] = (True, _)
        elif isinstance(item, Depend):
            async def _(c, x):
                ps = c[SUBSCRIBER].providers
                return (x in await item.fork(ps)(c)) if _left else (await item.fork(ps)(c) in x)
            self.__items[self.__last_key] = (True, _)
        else:
            if _left:
                async def _(c, x): return x in item
            else:
                async def _(c, x): return item in x
            self.__items[self.__last_key] = (True, _)
        return self

    def _not_contains(self, item, *, _left: bool = False):
        if isinstance(item, Deref):
            async def _(c, x): return (x not in await generate(item)(c)) if _left else (await generate(item)(c) not in x)
            self.__items[self.__last_key] = (True, _)
        elif isinstance(item, Depend):
            async def _(c, x):
                ps = c[SUBSCRIBER].providers
                return (x not in await item.fork(ps)(c)) if _left else (await item.fork(ps)(c) not in x)
            self.__items[self.__last_key] = (True, _)
        else:
            if _left:
                async def _(c, x): return x not in item
            else:
                async def _(c, x): return item not in x
            self.__items[self.__last_key] = (True, _)
        return self

    def __getitem__(self, item):
        if isinstance(item, Deref):
            async def _(c, x): return x[await generate(item)(c)]
            self.__items[self.__last_key] = (False, _)
        elif isinstance(item, Depend):
            async def _(c, x):
                ps = c[SUBSCRIBER].providers
                return x[await item.fork(ps)(c)]
            self.__items[self.__last_key] = (False, _)
        else:
            async def _(c, x): return x[item]
            self.__items[self.__last_key] = (False, _)
        return self

    def __or__(self, other):
        if isinstance(other, Deref):
            async def _(c, x): return x | await generate(other)(c)
            self.__items[self.__last_key] = (True, _)
        elif isinstance(other, Depend):
            async def _(c, x):
                ps = c[SUBSCRIBER].providers
                return x | await other.fork(ps)(c)
            self.__items[self.__last_key] = (True, _)
        else:
            async def _(c, x): return x | other
            self.__items[self.__last_key] = (True, _)
        return self

    def __and__(self, other):
        if isinstance(other, Deref):
            async def _(c, x): return x & await generate(other)(c)
            self.__items[self.__last_key] = (True, _)
        elif isinstance(other, Depend):
            async def _(c, x):
                ps = c[SUBSCRIBER].providers
                return x & await other.fork(ps)(c)
            self.__items[self.__last_key] = (True, _)
        else:
            async def _(c, x): return x & other
            self.__items[self.__last_key] = (True, _)
        return self

    def __xor__(self, other):
        if isinstance(other, Deref):
            async def _(c, x): return x ^ await generate(other)(c)
            self.__items[self.__last_key] = (True, _)
        elif isinstance(other, Depend):
            async def _(c, x):
                ps = c[SUBSCRIBER].providers
                return x ^ await other.fork(ps)(c)
            self.__items[self.__last_key] = (True, _)
        else:
            async def _(c, x): return x ^ other
            self.__items[self.__last_key] = (True, _)
        return self

    def __repr__(self):
        return repr(self.__items)

    def __iter__(self):
        return iter(self.__items.items())

    def __len__(self):
        return len(self.__items)


if TYPE_CHECKING:

    def generate(ref: Any) -> Callable[[Contexts], Any]: ...

    def in_(item: Any, target: Container[Any]) -> bool: ...

    def not_in(item: Any, target: Container[Any]) -> bool: ...

    def is_(ref: Any, value: Any) -> bool: ...

    def is_not(ref: Any, value: Any) -> bool: ...

    def not_(ref: Any) -> bool: ...

    def isinstance_(ref: Any, value: type | tuple[type, ...]) -> bool: ...

else:

    def generate(ref: Deref) -> Callable[[Contexts], Awaitable[Any]]:
        proxy_typ = ref._Deref__proxy_type

        async def _get(ctx: Contexts):
            item = next((v for v in ctx.values() if isinstance(v, proxy_typ)), ctx[EVENT])
            for key, value in ref:
                if key and (item := getattr(item, key, ctx.get(key, None))) is None:
                    return item
                if not value:
                    continue
                if value[0]:
                    return await value[1](ctx, item)
                item = await value[1](ctx, item)
            return item

        return _get

    def in_(item, target):
        assert any(isinstance(i, Deref) for i in (item, target)), "至少有一个参数需要是 Deref 类型"
        if not isinstance(target, Deref):
            return item.__contains__(target, _left=True)
        return target.__contains__(item)

    def not_in(item, target):
        assert any(isinstance(i, Deref) for i in (item, target)), "至少有一个参数需要是 Deref 类型"
        if not isinstance(target, Deref):
            return item._not_contains(target, _left=True)
        return target._not_contains(item)

    def is_(ref: Deref, value: Any):
        assert isinstance(ref, Deref), "第一个参数需要是 Deref 类型"
        return ref.__eq__(value, _is=True)

    def is_not(ref: Deref, value: Any):
        assert isinstance(ref, Deref), "第一个参数需要是 Deref 类型"
        return ref.__ne__(value, _is=True)

    def not_(ref: Deref):
        assert isinstance(ref, Deref), "参数需要是 Deref 类型"
        return ref.__bool__()

    def isinstance_(ref: Deref, value: Any):
        assert isinstance(ref, Deref), "第一个参数需要是 Deref 类型"
        return ref._isinstance(value)


def deref(proxy_type: type[T]) -> T:
    return cast(T, Deref(proxy_type))
