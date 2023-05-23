from typing import Generic, TypeVar, Callable, Any
from .typing import Contexts

T = TypeVar("T")


class Deref(Generic[T]):
    def __init__(self, proxy_type: type[T]):
        self.__proxy_type = proxy_type
        self.__items = {}
        self.__last_key = None

    def __getattr__(self, item):
        self.__items[item] = None
        self.__last_key = item
        return self

    def __call__(self, *args, **kwargs):
        if not self.__items:
            return self.__proxy_type(*args, **kwargs)
        self.__items[self.__last_key] = ("call", lambda x: x(*args, **kwargs))
        return self

    def __eq__(self, other):
        self.__items[self.__last_key] = lambda x: x == other
        return self

    def __ne__(self, other):
        self.__items[self.__last_key] = lambda x: x != other
        return self

    def __lt__(self, other):
        self.__items[self.__last_key] = lambda x: x < other
        return self

    def __gt__(self, other):
        self.__items[self.__last_key] = lambda x: x > other
        return self

    def __le__(self, other):
        self.__items[self.__last_key] = lambda x: x <= other
        return self

    def __ge__(self, other):
        self.__items[self.__last_key] = lambda x: x >= other
        return self

    def __contains__(self, item):
        self.__items[self.__last_key] = lambda x: item in x
        return self

    def __getitem__(self, item):
        self.__items[self.__last_key] = ("getitem", lambda x: x[item])
        return self

    def __or__(self, other):
        self.__items[self.__last_key] = lambda x: x | other
        return self

    def __and__(self, other):
        self.__items[self.__last_key] = lambda x: x & other
        return self

    def __xor__(self, other):
        self.__items[self.__last_key] = lambda x: x ^ other
        return self

    def __repr__(self):
        return repr(self.__items)

    def __iter__(self):
        return iter(self.__items.items())

    def __len__(self):
        return len(self.__items)


def generate(ref: Deref) -> Callable[[Contexts], Any]:
    if len(ref) == 0:
        return lambda x: x["event"]

    def _get(ctx: Contexts):
        item = ctx["event"]
        for key, value in ref:
            if not (item := getattr(item, key, ctx.get(key, None))):
                return item
            if isinstance(value, tuple):
                if value[0] == "call":
                    item = value[1](item)
                elif value[0] == "getitem":
                    item = value[1](item)
            elif callable(value):
                return value(item)
        return item

    return _get


def deref(proxy_type: type[T]) -> T:  # type: ignore
    return Deref(proxy_type)  # type: ignore
