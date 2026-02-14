from collections.abc import Container, Awaitable
from typing import TYPE_CHECKING, Any, TypeVar, cast, final
from collections.abc import Callable
import operator

from tarina import Empty

from .exceptions import STOP
from .typing import Contexts, Force
from .subscriber import Depend, SUBSCRIBER, ParamDepend

T = TypeVar("T")


def _make_op(op: Callable[[Any, Any], Any], is_terminal: bool = False):
    """通用运算符处理方法"""
    def wrapper(self, other):
        if isinstance(other, Deref):
            async def _(c, x): return op(x, await generate(other)(c))
        elif isinstance(other, Depend):
            async def _(c, x): return op(x, await other.fork(c[SUBSCRIBER].providers)(c))
        else:
            async def _(c, x): return op(x, other)
        _.__name__ = f"_{op.__name__}"
        _.__qualname__ = f"_make_op.<locals>.wrapper.<locals>._{op.__name__}"
        self._Deref__items.append((is_terminal, _))
        return self
    return wrapper


@final
class Deref:
    def __init__(self, proxy_type: type, name: str | None = None):
        self.__proxy_type = proxy_type
        self.__target_name = name
        self.__items: list[tuple[bool, str | Callable[[Contexts, Any], Awaitable[Any]]]] = []

    def __getattr__(self, item):
        self.__items.append((False, item))
        return self

    def _isinstance(self, item: type):
        async def _(c, x): return isinstance(x, item)
        self.__items.append((True, _))
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
        self.__items.append((False, _call))
        return self


    def __bool__(self):
        async def _(c, x): return bool(x)
        self.__items.append((True, _))
        return self

    def _not(self):
        # 如果上一个操作是终止操作，则将其改为非终止操作并添加一个新的终止操作来取反结果
        if self.__items and self.__items[-1][0]:
            __, func = self.__items[-1]
            self.__items[-1] = (False, func)
        async def _(c, x): return not bool(x)
        self.__items.append((True, _))
        return self

    __getitem__ = _make_op(operator.getitem)
    __add__ = _make_op(operator.add)
    __sub__ = _make_op(operator.sub)
    __mul__ = _make_op(operator.mul)
    __truediv__ = _make_op(operator.truediv)
    __floordiv__ = _make_op(operator.floordiv)
    __mod__ = _make_op(operator.mod)
    __lt__ = _make_op(operator.lt, True)
    __gt__ = _make_op(operator.gt, True)
    __le__ = _make_op(operator.le, True)
    __ge__ = _make_op(operator.ge, True)
    __or__ = _make_op(operator.or_, True)
    __and__ = _make_op(operator.and_, True)
    __xor__ = _make_op(operator.xor, True)
    __eq__ = _make_op(operator.eq, True)
    __ne__ = _make_op(operator.ne, True)

    _is_ = _make_op( operator.is_, True)
    _is_not = _make_op(operator.is_not, True)

    def __contains__(self, item, *, _left: bool = False):
        if isinstance(item, Deref):
            async def _contains(c, x): return (x in await generate(item)(c)) if _left else (await generate(item)(c) in x)
        elif isinstance(item, Depend):
            async def _contains(c, x):
                ps = c[SUBSCRIBER].providers
                return (x in await item.fork(ps)(c)) if _left else (await item.fork(ps)(c) in x)
        elif _left:
            async def _contains(c, x): return x in item
        else:
            async def _contains(c, x): return item in x
        self.__items.append((True, _contains))
        return self

    def __repr__(self):
        return repr(self.__items)

    def __iter__(self):
        return iter(self.__items)

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
        target_name = ref._Deref__target_name
        p = None
        if target_name is not None:
            p = ParamDepend(target_name, proxy_typ, Empty, True)

        async def _get(ctx: Contexts):
            if p is not None:
                item = await p.fork(ctx[SUBSCRIBER].providers)(ctx)
            else:
                item = next((v for v in ctx.values() if isinstance(v, proxy_typ)), None)
                if item is None and proxy_typ is not type(None):
                    raise STOP
            for is_terminal, value in ref:
                if isinstance(value, str):
                    if not hasattr(item, value):
                        raise STOP
                    item = getattr(item, value)
                else:
                    if is_terminal:
                        return await value(ctx, item)
                    item = await value(ctx, item)
            return Force(item) if item is None else item

        return _get

    def in_(item, target):
        assert any(isinstance(i, Deref) for i in (item, target)), "至少有一个参数需要是 Deref 类型"
        if not isinstance(target, Deref):
            return item.__contains__(target, _left=True)
        return target.__contains__(item)

    def not_in(item, target):
        assert any(isinstance(i, Deref) for i in (item, target)), "至少有一个参数需要是 Deref 类型"
        if not isinstance(target, Deref):
            return item.__contains__(target, _left=True)._not()
        return target.__contains__(item)._not()

    def is_(ref: Deref, value: Any):
        assert isinstance(ref, Deref), "第一个参数需要是 Deref 类型"
        return ref._is_(value)

    def is_not(ref: Deref, value: Any):
        assert isinstance(ref, Deref), "第一个参数需要是 Deref 类型"
        return ref._is_not(value)

    def not_(ref: Deref):
        assert isinstance(ref, Deref), "参数需要是 Deref 类型"
        return ref._not()

    def isinstance_(ref: Deref, value: Any):
        assert isinstance(ref, Deref), "第一个参数需要是 Deref 类型"
        return ref._isinstance(value)


def deref(typ: type[T], name: str | None = None) -> T:
    return cast(T, Deref(typ, name))
