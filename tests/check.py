from functools import wraps
from typing import Callable, TypeVar
from typing_extensions import Concatenate, ParamSpec

from arclet.cithun import NodeState, User

T = TypeVar("T")
P = ParamSpec("P")

user = User("cithun")


def require(path: str, missing_ok: bool = False) -> Callable[[Callable[P, T]], Callable[Concatenate[User, P], T]]:
    def decorator(func: Callable[P, T]) -> Callable[Concatenate[User, P], T]:
        @wraps(func)
        def wrapper(usr: User, *args: P.args, **kwargs: P.kwargs) -> T:
            if usr.require(path, missing_ok=missing_ok):
                return func(*args, **kwargs)
            else:
                raise PermissionError(f"Permission denied for {usr.name} to access {path}")

        return wrapper

    return decorator


@require("/foo/bar/baz")
def alice():
    print("alice")


@require("/foo/bar/baz/qux", missing_ok=True)
def bob():
    print("bob")


@require("/foo/bar/baz/qux", missing_ok=False)
def caven():
    print("caven")


user.sadd("/foo/bar/baz", NodeState("vma"))
alice(user)  # alice
bob(user)  # bob as target node's parent is available

try:
    caven(user)
except PermissionError as e:
    # raise PermissionError as caven specified missing_ok=False, and baz/qux is not exist
    print(e)

user.smodify("/foo/bar/", NodeState("v--"))

try:
    alice(user)
except PermissionError as e:
    print(e)  # raise PermissionError as alice's target node is not available
