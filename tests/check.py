from functools import wraps
from pathlib import Path
from typing import Callable, TypeVar
from typing_extensions import Concatenate, ParamSpec

from arclet.cithun import User, Role, Permission
from arclet.cithun.builtins import System

monitor = System(Path("check_monitor.json"))

T = TypeVar("T")
P = ParamSpec("P")

user = monitor.store.add_user(User("user:cithun", "cithun"))


def require(
    path: str, default_available: bool = False
) -> Callable[[Callable[P, T]], Callable[Concatenate[User, P], T]]:
    def decorator(func: Callable[P, T]) -> Callable[Concatenate[User, P], T]:
        @wraps(func)
        def wrapper(usr: User, *args: P.args, **kwargs: P.kwargs) -> T:
            if monitor.test(user, path, Permission.AVAILABLE):
                return func(*args, **kwargs)
            else:
                raise PermissionError(f"Permission denied for {usr.name} to access {path}")

        return wrapper

    monitor.store.define(path)
    return decorator


@require("foo.bar.baz")
def alice():
    return "alice"


@require("foo.bar.baz.qux")
def bob():
    return "bob"


# ROOT.set(user, "foo.bar.baz.*", NodeState("vma"))
monitor.suset(user, "foo.bar.baz", Permission.VISIT | Permission.AVAILABLE)
monitor.suset(user, "foo.bar.baz.qux", Permission.VISIT | Permission.AVAILABLE)
assert alice(user) == "alice"
assert bob(user) == "bob"  # target node's parent is available


@require("foo.bar.qux")
def caven():
    return "caven"


# @require("foo.bar.baz.quux")
# def dale():
#     return "dale"
#
#
# assert dale(user) == "dale"  # target node defined after the wildcard set is also available

try:
    caven(user)
except PermissionError as e:
    # raise PermissionError as caven's target node is not in the available path
    assert str(e) == "Permission denied for cithun to access foo.bar.qux"

user_qux = monitor.suset(user, "foo.bar.qux", Permission.VISIT | Permission.AVAILABLE | Permission.MODIFY)
assert caven(user) == "caven"  # caven as target node is available

monitor.store.depend(user_qux, user, "foo.bar.baz.qux", Permission.VISIT)
monitor.suset(user, "foo.bar.baz.qux", Permission.VISIT)
try:
    caven(user)
except PermissionError as e:
    # raise PermissionError as caven's target node is dependent on the unavailable node
    assert str(e) == "Permission denied for user:cithun to access foo.bar.qux"
