import inspect
from dataclasses import dataclass
from typing import Annotated, get_args
from typing_extensions import Doc

import pytest
from tarina import Empty
from tarina.generic import get_origin, origin_is_union

import arclet.letoderea as le


@dataclass
class CallEvent:
    called: str
    user: str
    content: str
    params: dict

    def check_result(self, value) -> le.Result[str] | None: ...


pub = le.define(CallEvent, name="called_event")


@pytest.mark.asyncio
async def test_check():
    subs = []
    available_functions = {}
    mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        set: "array",
        tuple: "array",
        dict: "object",
    }

    @pub.gather
    async def _(ev, ctx):
        ctx.update(ev.params)
        return ctx

    @pub.check
    def c(_, sub: le.Subscriber):
        if not (description := inspect.cleandoc(sub.__doc__ or "")):
            return False
        properties = {}
        required = []
        for param in sub.params:
            if param.providers:  # skip provided parameters
                continue
            if param.default is Empty:
                required.append(param.name)
            anno = param.annotation
            orig = get_origin(anno)
            if origin_is_union(orig) and type(None) in get_args(anno):  # pragma: no cover
                t = get_args(anno)[0]
            else:
                t = anno
            documentation = ""
            if get_origin(t) is Annotated:  # pragma: no cover
                t, *meta = get_args(t)
                if doc := next((i for i in meta if isinstance(i, Doc)), None):
                    documentation = doc.documentation
            properties[param.name] = {
                "title": param.name.title(),
                "type": mapping.get(get_origin(t), "object"),
                "description": documentation,
            }

        subs.append(
            {
                "type": "function",
                "function": {
                    "name": sub.__name__,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                        "additionalProperties": False,
                    }
                }
            }
        )
        available_functions[sub.__name__] = lambda **kwargs: kwargs
        le.enter_if(le.deref(CallEvent).called == sub.__name__)(sub)
        return True

    @le.on(CallEvent)
    async def no_doc(name: str):  # pragma: no cover
        return f"Hello {name}!"

    @le.on(CallEvent)
    async def get_hello(event: CallEvent, name: Annotated[str, Doc("user name")], msg: str = "Hello"):
        """Get a hello message for a user."""
        return f"{msg} {name}!"

    assert subs[0] == {
        "type": "function",
        "function": {
            "name": "get_hello",
            "description": "Get a hello message for a user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "title": "Name",
                        "type": "string",
                        "description": "user name",
                    },
                    "msg": {
                        "title": "Msg",
                        "type": "string",
                        "description": "",
                    },
                },
                "required": ["name"],
                "additionalProperties": False,
            }
        }
    }

    # Simulate a call, in which we already get the parameters from the LLM
    response = available_functions["get_hello"](name="Bill")

    async for result in le.waterfall(CallEvent("get_hello", "Bill", "Hello!", response)):
        assert result
        assert result.value == "Hello Bill!"


@dataclass
class ValidateEvent:
    called: str
    user: str


@pytest.mark.asyncio
async def test_validate():
    pub = le.define(ValidateEvent, name="validated_event")
    pub1 = le.define(ValidateEvent, validator=lambda x: x.called == "test" and x.user == "test", name="validated_event/test")

    @le.use("validated_event")
    async def _(called: str, user: str):
        """Get a message for a user."""
        return f"{called!r} by {user}"

    @le.use("validated_event/test")
    async def _(called: str, user: str):
        """Get a message for a user, but only if the called is 'test' and the user is 'test"""
        return f"{called!r} by {user} and must be test"

    result1 = [res.value async for res in le.waterfall(ValidateEvent("test", "test"))]
    result2 = [res.value async for res in le.waterfall(ValidateEvent("test", "not_test"))]
    assert result1 == ["'test' by test", "'test' by test and must be test"]
    assert result2 == ["'test' by not_test"]
