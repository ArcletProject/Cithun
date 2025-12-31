from collections.abc import Callable
from functools import reduce
from operator import or_
import fnmatch
import re
from typing import TypeAlias, TypeVar, overload

from arclet.cithun import Permission, PermissionEngine, ResourceNode, Role, User

Attach: TypeAlias = (
    "Callable[[User, dict | None, Permission, Callable[[User | Role, dict | None], Permission]], Permission]"
)
TAttach = TypeVar("TAttach", bound=Attach)
Attach1: TypeAlias = (
    "Callable[[User, str, dict | None, Permission, Callable[[User | Role, dict | None], Permission]], Permission]"
)
TAttach1 = TypeVar("TAttach1", bound=Attach1)


class Attacher:
    def __init__(self, engine: PermissionEngine[dict]):
        self.attachs = []
        engine.register_strategy(self._run_attachs)

    def _run_attachs(
        self,
        user: User,
        resource: ResourceNode,
        context: dict | None,
        current_mask: Permission,
        permission_lookup: Callable[[User | Role, dict | None], Permission],
    ) -> Permission:
        results = []
        for pattern, func in self.attachs:
            if pattern(resource.id):
                results.append(func(user, resource.id, context, current_mask, permission_lookup))
        if not results:
            return current_mask
        return reduce(or_, results, current_mask)

    @overload
    def attach(self, pattern: str) -> Callable[[TAttach], TAttach]: ...

    @overload
    def attach(self, pattern: Callable[[str], bool]) -> Callable[[TAttach1], TAttach1]: ...

    def attach(self, pattern):  # type: ignore
        if isinstance(pattern, str):

            def decorator(func: Attach, /):
                if re.search(r"[*?\[\]]", pattern):
                    predicate = lambda p: fnmatch.fnmatch(p, pattern)
                else:
                    predicate = lambda p: p == pattern
                self.attachs.append((predicate, lambda u, _, *args: func(u, *args)))
                return func

            return decorator

        def wrapper(func: Attach1, /):
            self.attachs.append((pattern, func))
            return func

        return wrapper
