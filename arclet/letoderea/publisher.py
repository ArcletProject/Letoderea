from __future__ import annotations

from asyncio import Queue
from contextlib import suppress
from typing import Any, Callable, TypeVar, ClassVar, overload

from .auxiliary import BaseAuxiliary
from .context import publisher_ctx
from .event import BaseEvent, get_auxiliaries, get_providers
from .handler import dispatch
from .provider import Param, Provider, ProviderFactory
from .subscriber import Subscriber
from .typing import Contexts

global_providers: list[Provider] = []

T = TypeVar("T")


class EventProvider(Provider[BaseEvent]):
    EVENT_CLASS: ClassVar[type] = BaseEvent

    def validate(self, param: Param):
        return (isinstance(param.annotation, type) and issubclass(param.annotation, self.EVENT_CLASS)) or param.name == "event"

    async def __call__(self, context: Contexts) -> BaseEvent | None:
        return context.get("$event")


class ContextProvider(Provider[Contexts]):
    def validate(self, param: Param):
        return param.annotation is Contexts

    async def __call__(self, context: Contexts) -> Contexts:
        return context


global_providers.extend([EventProvider(), ContextProvider()])


class Publisher:
    id: str
    subscribers: list[Subscriber]
    providers: list[Provider | ProviderFactory]
    auxiliaries: list[BaseAuxiliary]

    def __init__(
        self,
        id_: str,
        *events: type[BaseEvent],
        predicate: Callable[[Any], bool] | None = None,
        queue_size: int = -1,
    ):
        self.id = f"{id_}::{sorted(events, key=lambda e: id(e))}"
        self.event_queue = Queue(queue_size)
        self.subscribers = []
        self.providers = []
        self.auxiliaries = []

        if not events:
            if not predicate:
                raise ValueError("events cannot be None")
            self.validate = predicate
        else:
            for event in events:
                self.providers.extend(get_providers(event))
                self.auxiliaries.extend(get_auxiliaries(event))
            if predicate:
                self.id += f"::{predicate}"
                self.validate = lambda e: isinstance(e, events) and predicate(e)
            else:
                self.validate = lambda e: isinstance(e, events)

    def __repr__(self):
        return f"{self.__class__.__name__}::{self.id}"

    async def publish(self, event: BaseEvent) -> Any:
        """主动向自己的订阅者发布事件"""
        await dispatch(self.subscribers, event)

    def unsafe_push(self, event: BaseEvent) -> None:
        """将事件放入队列，等待被 event system 主动轮询; 该方法可能引发 QueueFull 异常"""
        self.event_queue.put_nowait(event)

    async def push(self, event: BaseEvent):
        """将事件放入队列，等待被 event system 主动轮询"""
        await self.event_queue.put(event)

    async def supply(self) -> BaseEvent | None:
        """被动提供事件方法， 由 event system 主动轮询"""
        return await self.event_queue.get()

    def add_subscriber(self, subscriber: Subscriber) -> None:
        """
        添加订阅者
        """
        self.subscribers.append(subscriber)

    def remove_subscriber(self, subscriber: Subscriber) -> None:
        """
        移除订阅者
        """
        with suppress(ValueError):
            self.subscribers.remove(subscriber)

    def bind(
        self,
        *args: BaseAuxiliary | Provider | type[Provider] | ProviderFactory | type[ProviderFactory],
    ) -> None:
        """为发布器增加间接 Provider 或 Auxiliaries"""
        self.auxiliaries.extend(a for a in args if isinstance(a, BaseAuxiliary))
        providers = [p for p in args if not isinstance(p, BaseAuxiliary)]
        self.providers.extend(p() if isinstance(p, type) else p for p in providers)

    def unbind(
        self,
        arg: Provider | BaseAuxiliary | type[Provider] | ProviderFactory | type[ProviderFactory],
    ) -> None:
        """移除发布器的间接 Provider 或 Auxiliaries"""
        if isinstance(arg, BaseAuxiliary):
            with suppress(ValueError):
                self.auxiliaries.remove(arg)
        elif isinstance(arg, (ProviderFactory, Provider)):
            with suppress(ValueError):
                self.providers.remove(arg)
        else:
            for p in self.providers.copy():
                if isinstance(p, arg):
                    self.providers.remove(p)

    def __enter__(self):
        self._token = publisher_ctx.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        publisher_ctx.reset(self._token)

    @overload
    def register(
        self,
        func: Callable[..., Any],
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
    ) -> Subscriber:
        ...

    @overload
    def register(
        self,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
    ) -> Callable[[Callable[..., Any]], Subscriber]:
        ...

    def register(
        self,
        func: Callable[..., Any] | None = None,
        *,
        priority: int = 16,
        auxiliaries: list[BaseAuxiliary] | None = None,
        providers: list[Provider | type[Provider] | ProviderFactory | type[ProviderFactory]] | None = None,
    ):
        """注册一个订阅者"""
        auxiliaries = auxiliaries or []
        providers = providers or []

        def register_wrapper(exec_target: Callable, /) -> Subscriber:
            _providers = [
                *global_providers,
                *self.providers,
                *providers,
            ]
            _auxiliaries = [
                *self.auxiliaries,
                *auxiliaries,
            ]
            res = Subscriber(
                exec_target,
                priority=priority,
                auxiliaries=_auxiliaries,
                providers=_providers,
                dispose=self.remove_subscriber,
            )
            self.add_subscriber(res)
            return res

        if func:
            return register_wrapper(func)
        return register_wrapper

    def __iadd__(self, other):
        if isinstance(other, Subscriber):
            self.add_subscriber(other)
        elif callable(other):
            self.register()(other)
        else:
            raise TypeError(f"unsupported operand type(s) for +=: 'Publisher' and '{other.__class__.__name__}'")
        return self


class BackendPublisher(Publisher):
    def __init__(
        self,
        id_: str,
        predicate: Callable[[Any], bool] | None = None,
        queue_size: int = -1,
    ):
        self.id = id_
        if predicate:
            self.id += f"::{predicate}"
            self.validate = predicate
        else:
            self.validate = lambda e: True
        self.event_queue = Queue(queue_size)
        self.subscribers = []
        self.providers = []
        self.auxiliaries = []


class ExternalPublisher(Publisher):
    """宽松的发布器，任意对象都可以作为事件被发布"""

    def __init__(
        self,
        target: type[T],
        supplier: Callable[[T], dict[str, Any]] | None = None,
        predicate: Callable[[T], bool] | None = None,
        queue_size: int = -1,
    ):
        self.id = f"{target.__name__}_{id(target)}"
        if predicate:
            self.id += f"::{predicate}"
            self.validate = lambda e: isinstance(e, target) and predicate(e)
        else:
            self.validate = lambda e: isinstance(e, target)
        self.event_queue = Queue(queue_size)
        self.subscribers = []
        self.providers = []
        self.auxiliaries = []
        self.target = target

        class _FakeEvent:
            async def gather(self, context):
                if supplier:
                    context.update(supplier(context["$event"]))
                return context

        self._fake_event_cls = _FakeEvent

    def add_subscriber(self, subscriber: Subscriber) -> None:
        subscriber.external_source = lambda e: self._fake_event_cls()
        self.subscribers.append(subscriber)
