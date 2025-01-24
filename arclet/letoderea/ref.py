from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar, cast

from .event import EVENT
from .typing import Contexts

T = TypeVar("T")


class Deref:
    def __init__(self, proxy_type: type):
        self.__proxy_type = proxy_type
        self.__items: dict[Optional[str], Optional[tuple[bool, Callable[[Any], Any]]]] = {}
        self.__last_key = None

    def __getattr__(self, item):
        self.__items[item] = None
        self.__last_key = item
        return self

    def __call__(self, *args, **kwargs):
        self.__items[self.__last_key] = (False, lambda x: x(*args, **kwargs))
        return self

    def _not(self):
        self.__items[self.__last_key] = (True, lambda x: bool(x))
        return self

    def __eq__(self, other, *, _is: bool = False):  # type: ignore
        if _is:
            self.__items[self.__last_key] = (True, lambda x: x is other)
        else:
            self.__items[self.__last_key] = (True, lambda x: x == other)
        return self

    def __ne__(self, other, *, _is: bool = False):  # type: ignore
        if _is:
            self.__items[self.__last_key] = (True, lambda x: x is not other)
        else:
            self.__items[self.__last_key] = (True, lambda x: x != other)
        return self

    def __lt__(self, other):
        self.__items[self.__last_key] = (True, lambda x: x < other)
        return self

    def __gt__(self, other):
        self.__items[self.__last_key] = (True, lambda x: x > other)
        return self

    def __le__(self, other):
        self.__items[self.__last_key] = (True, lambda x: x <= other)
        return self

    def __ge__(self, other):
        self.__items[self.__last_key] = (True, lambda x: x >= other)
        return self

    def __contains__(self, item):
        self.__items[self.__last_key] = (True, lambda x: item in x)
        return self

    def __getitem__(self, item):
        self.__items[self.__last_key] = (False, lambda x: x[item])
        return self

    def __or__(self, other):
        self.__items[self.__last_key] = (True, lambda x: x | other)
        return self

    def __and__(self, other):
        self.__items[self.__last_key] = (True, lambda x: x & other)
        return self

    def __xor__(self, other):
        self.__items[self.__last_key] = (True, lambda x: x ^ other)
        return self

    def __repr__(self):
        return repr(self.__items)

    def __iter__(self):
        return iter(self.__items.items())

    def __len__(self):
        return len(self.__items)


if TYPE_CHECKING:

    def generate(ref: Any) -> Callable[[Contexts], Any]: ...


    def is_(ref: Any, value: Any) -> bool: ...

    def is_not(ref: Any, value: Any) -> bool: ...

    def not_(ref: Any) -> bool: ...

else:

    def generate(ref: Deref) -> Callable[[Contexts], Any]:
        if len(ref) == 0:
            return lambda x: x[EVENT]

        def _get(ctx: Contexts):
            item = ctx[EVENT]
            for key, value in ref:
                if key and (item := getattr(item, key, ctx.get(key, None))) is None:
                    return item
                if not value:
                    continue
                if value[0]:
                    return value[1](item)
                item = value[1](item)
            return item

        return _get

    def is_(ref: Deref, value: Any):
        return ref.__eq__(value, _is=True)

    def is_not(ref: Deref, value: Any):
        return ref.__ne__(value, _is=True)

    def not_(ref: Deref):
        return ref._not()


def deref(proxy_type: type[T]) -> T:
    return cast(T, Deref(proxy_type))
