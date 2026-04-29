import pytest

from arclet.letoderea import scope
from arclet.letoderea.scope import scope_ctx
from arclet.letoderea.exceptions import ExceptionHandler


def pytest_runtest_setup(item):
    ExceptionHandler.print_traceback = False
    return None


@pytest.fixture(autouse=True, scope="function")
def _reset_scope(request):
    _scope = scope.Scope.of(f"test_scope_{request.node.name}")
    token = scope_ctx.set(_scope)
    yield
    scope_ctx.reset(token)
    scopes = list(scope._scopes.values())
    for sp in scopes:
        if sp.id == "$global":
            continue
        sp.dispose()
