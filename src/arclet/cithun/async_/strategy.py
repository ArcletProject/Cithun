from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Generic, Protocol, TypeVar

from arclet.cithun.model import Permission, ResourceNode, Role, User

T = TypeVar("T")


class AsyncPermissionStrategy(Protocol[T]):
    """权限策略协议。"""

    async def __call__(
        self,
        user: User,
        resource: ResourceNode,
        context: T | None,
        current_mask: Permission,
        permission_lookup: Callable[[User | Role, T | None], Awaitable[Permission]],
    ) -> Permission:
        """执行策略。

        Args:
            user (User): 用户对象。
            resource (ResourceNode): 资源节点。
            context (T, optional): 上下文信息。
            current_mask (Permission): 当前权限掩码。
            permission_lookup (Callable[[User | Role, T | None], Awaitable[Permission]]): 权限查找回调函数。

        Returns:
            Permission: 更新后的权限掩码。
        """
        ...


class AsyncPermissionEngine(Generic[T]):
    """权限引擎，管理和应用权限策略。"""

    def __init__(self):
        self._strategies: list[AsyncPermissionStrategy[T]] = []

    def register_strategy(self, strategy: AsyncPermissionStrategy[T]):
        """注册策略。

        Args:
            strategy (AsyncPermissionStrategy[T]): 策略对象。
        """
        self._strategies.append(strategy)

    async def apply_strategies(
        self,
        user: User,
        resource: ResourceNode,
        context: T | None,
        mask: Permission,
        permission_lookup: Callable[[User | Role, T | None], Awaitable[Permission]],
    ) -> Permission:
        """应用所有注册的策略。

        Args:
            user (User): 用户对象。
            resource (ResourceNode): 资源节点。
            context (T, optional): 上下文信息。
            mask (Permission): 初始权限掩码。
            permission_lookup (Callable[[User | Role, T | None], Awaitable[Permission]]): 权限查找回调函数。

        Returns:
            Permission: 最终权限掩码。
        """
        for s in self._strategies:
            mask = await s(user, resource, context, mask, permission_lookup)
        return mask
