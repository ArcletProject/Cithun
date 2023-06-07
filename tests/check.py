from arclet.cithun import User, NodeState
from typing import Callable, TypeVar
from functools import wraps
from typing_extensions import ParamSpec, Concatenate

T = TypeVar('T')
P = ParamSpec('P')

user = User('cithun')


def perm_add(usr: User, path: str, active: bool = True):
    return usr.sadd(path, NodeState(7) if active else None)


def perm_set(usr: User, path: str, state: NodeState):
    return usr.smodify(path, state)


def require(path: str, missing_ok: bool = True) -> Callable[[Callable[P, T]], Callable[Concatenate[User, P], T]]:
    def decorator(func: Callable[P, T]) -> Callable[Concatenate[User, P], T]:
        @wraps(func)
        def wrapper(usr: User, *args: P.args, **kwargs: P.kwargs) -> T:
            if usr.require(path, missing_ok=missing_ok):
                return func(*args, **kwargs)
            else:
                raise PermissionError(f"Permission denied for {usr.name} to access {path}")
        return wrapper

    return decorator


@require("/foo/bar/baz/qux")
def foo():
    print("foo")


@require("/foo/bar/baz/qux/quux")
def bar():
    print("bar")


@require("/foo/bar/baz/qux/quux", missing_ok=False)
def baz():
    print("baz")


perm_add(user, "/foo/bar/baz/qux")
foo(user)  # foo
bar(user)  # bar as target node's parent is available

try:
    baz(user)
except PermissionError as e:
    print(e)  # raise PermissionError as baz specified missing_ok=False, and qux/quux is not available

perm_set(user, "/foo/bar/baz/", NodeState("v--"))

try:
    foo(user)
except PermissionError as e:
    print(e)  # raise PermissionError as foo's target node is not available
