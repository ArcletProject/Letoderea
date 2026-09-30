import pytest_asyncio

from arclet.letoderea import scope
from arclet.letoderea.exceptions import ExceptionHandler
from arclet.letoderea.scope import scope_ctx


def pytest_runtest_setup(item):
    ExceptionHandler.print_traceback = False
    return None


@pytest_asyncio.fixture(autouse=True, scope="function")
async def _reset_scope(request):
    if request.node.get_closest_marker("no_scope"):
        yield
        return
    _scope = scope.Scope.of(f"test_scope_{request.node.name}")
    token = scope_ctx.set(_scope)
    yield
    scope_ctx.reset(token)
    await _scope.cleanup()
