from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, Generic
from typing_extensions import TypeVarTuple, Unpack


Ts = TypeVarTuple("Ts")


from .model import User, Role, ResourceNode


class PermissionStrategy(Protocol[Unpack[Ts]]):
    def __call__(
        self,
        user: User,
        resource: ResourceNode,
        context: tuple[Unpack[Ts]],
        current_mask: int,
        permission_lookup: Callable[[User | Role, Unpack[Ts]], int],
    ) -> int:
        ...

class PermissionEngine(Generic[Unpack[Ts]]):
    def __init__(self):
        self._strategies: list[PermissionStrategy[Unpack[Ts]]] = []

    def register_strategy(self, strategy: PermissionStrategy[Unpack[Ts]]):
        self._strategies.append(strategy)

    def apply_strategies(
        self,
        user: User,
        resource: ResourceNode,
        context: tuple[Unpack[Ts]],
        mask: int,
        permission_lookup: Callable[[User | Role, Unpack[Ts]], int],
    ) -> int:
        for s in self._strategies:
            mask = s(user, resource, context, mask, permission_lookup)
        return mask
