from arclet.letoderea import es
from arclet.letoderea.scope import Scope, _scopes
from arclet.letoderea.publisher import _publishers
from arclet.letoderea.exceptions import ExceptionHandler


def pytest_runtest_setup(item):
    ExceptionHandler.print_traceback = False
    return None


def pytest_runtest_teardown(item):
    scopes = list(_scopes.values())
    for sp in scopes:
        sp.dispose()
    _scopes["$global"] = es._global_scope = Scope("$global")
    return None
