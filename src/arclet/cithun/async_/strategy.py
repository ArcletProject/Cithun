from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Generic, Protocol
from typing_extensions import TypeVarTuple, Unpack

from arclet.cithun.model import ResourceNode, Role, User

Ts = TypeVarTuple("Ts")


class AsyncPermissionStrategy(Protocol[Unpack[Ts]]):
    """权限策略协议。"""

    async def __call__(
        self,
        user: User,
        resource: ResourceNode,
        context: tuple[Unpack[Ts]],
        current_mask: int,
        permission_lookup: Callable[[User | Role, Unpack[Ts]], Awaitable[int]],
    ) -> int:
        """执行策略。

        Args:
            user (User): 用户对象。
            resource (ResourceNode): 资源节点。
            context (tuple[Unpack[Ts]]): 上下文信息。
            current_mask (int): 当前权限掩码。
            permission_lookup (Callable[[User | Role, Unpack[Ts]], Awaitable[int]]): 权限查找回调函数。

        Returns:
            int: 更新后的权限掩码。
        """
        ...


class AsyncPermissionEngine(Generic[Unpack[Ts]]):
    """权限引擎，管理和应用权限策略。"""

    def __init__(self):
        self._strategies: list[AsyncPermissionStrategy[Unpack[Ts]]] = []

    def register_strategy(self, strategy: AsyncPermissionStrategy[Unpack[Ts]]):
        """注册策略。

        Args:
            strategy (AsyncPermissionStrategy[Unpack[Ts]]): 策略对象。
        """
        self._strategies.append(strategy)

    async def apply_strategies(
        self,
        user: User,
        resource: ResourceNode,
        context: tuple[Unpack[Ts]],
        mask: int,
        permission_lookup: Callable[[User | Role, Unpack[Ts]], Awaitable[int]],
    ) -> int:
        """应用所有注册的策略。

        Args:
            user (User): 用户对象。
            resource (ResourceNode): 资源节点。
            context (tuple[Unpack[Ts]]): 上下文信息。
            mask (int): 初始权限掩码。
            permission_lookup (Callable[[User | Role, Unpack[Ts]], Awaitable[int]]): 权限查找回调函数。

        Returns:
            int: 最终权限掩码。
        """
        for s in self._strategies:
            mask = await s(user, resource, context, mask, permission_lookup)
        return mask
