import asyncio
from typing import Type, Union, Callable, Optional
from ..handler import await_exec_target
from ..utils import search_event
from ..entities.event import TemplateEvent, ParamRet
from ..entities.condition import EventCondition


class StepOut(EventCondition):
    event_type: Type[TemplateEvent]
    handler: Callable
    target_args_handler: Union[Callable[[], ParamRet], ParamRet]

    def judge(self, event: TemplateEvent) -> bool:
        if type(event) is self.event_type:
            self.target_args_handler = event.get_params
            return True
        return False

    def __init__(self, event: Union[Type[TemplateEvent], str]):
        if isinstance(event, str):
            name = event
            event = search_event(event)
            if not event:
                raise Exception(name + " cannot found!")
        self.event_type = event
        self._future: Optional[asyncio.Future] = None
        self._waited: bool = False

    def __del__(self):
        if self._future:
            self._future.cancel()

    @staticmethod
    def handler(*args, **kwargs):
        pass

    def __call__(self, func: Callable):
        setattr(self, 'handler', func)
        return self

    @property
    def future(self):
        return self._future

    def done(self) -> bool:
        """触发器是否已经完成。"""
        return self._waited or bool(self._future and self._future.done())

    async def make_done(self):
        if self.done():
            return False
        try:
            result = await await_exec_target(
                self.handler,
                self.target_args_handler
            )
            if result is not None and not self._future.done():
                self._future.set_result(result)
                return True
        except Exception as e:
            if not self._future.done():
                self._future.set_exception(e)
                return True
        return False

    async def wait(self, timeout: float = 0.):
        if self._waited:
            raise RuntimeError('已被等待。')

        if self._future is None:
            self._future = asyncio.get_running_loop().create_future()

        try:
            if timeout > 0:
                return await asyncio.wait_for(self._future, timeout)
            else:
                return await self._future
        except asyncio.TimeoutError:
            return None
        finally:
            self._waited = self._future.done()
