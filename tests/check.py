from functools import wraps
from pathlib import Path
from typing import Callable, TypeVar
from typing_extensions import Concatenate, ParamSpec

from arclet.cithun import ROOT, NodeState, define, depend
from arclet.cithun.builtins.monitor import DefaultMonitor
from arclet.cithun.builtins.owner import DefaultOwner

monitor = DefaultMonitor(Path("check_monitor.json"))

T = TypeVar("T")
P = ParamSpec("P")

user = monitor.get_or_new_owner("user:cithun")


def require(
    path: str, default_available: bool = False
) -> Callable[[Callable[P, T]], Callable[Concatenate[DefaultOwner, P], T]]:
    def decorator(func: Callable[P, T]) -> Callable[Concatenate[DefaultOwner, P], T]:
        @wraps(func)
        def wrapper(usr: DefaultOwner, *args: P.args, **kwargs: P.kwargs) -> T:
            state = ROOT.get(usr, path)
            if state.available:
                return func(*args, **kwargs)
            else:
                raise PermissionError(f"Permission denied for {usr.name} to access {path}")

        return wrapper

    define(path)
    ROOT.set(monitor.default_group, path, NodeState("vma") if default_available else NodeState("v--"))
    return decorator


@require("foo.bar.baz")
def alice():
    return "alice"


@require("foo.bar.baz.qux")
def bob():
    return "bob"


@require("foo.bar.qux")
def caven():
    return "caven"


ROOT.set(user, "foo.bar.baz.*", NodeState("vma"))
assert alice(user) == "alice"
assert bob(user) == "bob"  # target node's parent is available

try:
    caven(user)
except PermissionError as e:
    # raise PermissionError as caven's target node is not in the available path
    assert str(e) == "Permission denied for user:cithun to access foo.bar.qux"

ROOT.set(user, "foo.bar.qux", NodeState("vma"))
assert caven(user) == "caven"  # caven as target node is available

depend("foo.bar.qux", "foo.bar.baz.qux")
ROOT.set(user, "foo.bar.baz.qux", NodeState("v--"))

try:
    caven(user)
except PermissionError as e:
    # raise PermissionError as caven's target node is dependent on the unavailable node
    assert str(e) == "Permission denied for user:cithun to access foo.bar.qux"
