from typing import Callable, Optional, List, Dict, Any
from .auxiliary import BaseAuxiliary
from .event import TemplateEvent
from ..utils import argument_analysis


class Subscriber:
    callable_target: Callable
    subscriber_name: str
    auxiliaries: Optional[List[BaseAuxiliary]]
    internal_arguments: Dict[type, Any]
    revise_dispatches: Dict[str, str]

    def __init__(
        self,
        callable_target: Callable,
        *,
        subscriber_name: Optional[str] = None,
        auxiliaries: Optional[List[BaseAuxiliary]] = None,
        **kwargs,
    ) -> None:
        self.callable_target = callable_target
        self.subscriber_name = subscriber_name or callable_target.__name__
        if hasattr(callable_target, "__auxiliaries__"):
            self.auxiliaries = getattr(callable_target, "__auxiliaries__", []) + (
                auxiliaries or []
            )
        elif hasattr(self, "auxiliaries"):
            self.auxiliaries += auxiliaries or []
        else:
            self.auxiliaries = auxiliaries or []
        self.params = argument_analysis(self.callable_target)
        self.internal_arguments = TemplateEvent.param_export(**kwargs)
        self.revise_dispatches = {}

    def __call__(self, *args, **kwargs):
        return self.callable_target(*args, **kwargs)

    def __repr__(self):
        return f"Subscriber[{self.subscriber_name}]"

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        if isinstance(other, Subscriber):
            return other.name == self.subscriber_name
        elif isinstance(other, str):
            return other == self.subscriber_name

    @property
    def name(self):
        return self.subscriber_name

    @name.setter
    def name(self, new_name):
        self.subscriber_name = new_name
