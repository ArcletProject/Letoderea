from arclet.letoderea import scope
from arclet.letoderea.exceptions import ExceptionHandler


def pytest_runtest_setup(item):
    ExceptionHandler.print_traceback = False
    return None


def pytest_runtest_teardown(item):
    scopes = list(scope._scopes.values())
    for sp in scopes:
        sp.dispose()
    scope._scopes["$global"] = scope.Scope("$global")
    return None
