from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar, overload

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


@dataclass(eq=True, frozen=True)
class AclDependency(Generic[T]):
    """描述一个 ACL 对“另一个 subject 在某资源上的权限”的依赖。"""

    target_resource_id: str
    depend_resource_id: str
    target_subject: User | Role | Callable[[T | None, User | Role], Awaitable[bool]] | None = None
    depend_subject: User | Role | Callable[[T | None, User | Role], Awaitable[User | Role]] | None = None
    required_mask: Permission = Permission.AVAILABLE

    async def check_target_subject(self, context: T | None, current_subject: User | Role) -> bool:
        if self.target_subject is None:
            return True
        elif callable(self.target_subject):
            return await self.target_subject(context, current_subject)
        else:
            return self.target_subject == current_subject

    async def get_depend_subject(self, context: T | None, current_subject: User | Role) -> User | Role:
        if self.depend_subject is None:
            return current_subject
        elif callable(self.depend_subject):
            return await self.depend_subject(context, current_subject)
        else:
            return self.depend_subject


class AsyncPermissionEngine(Generic[T]):
    """权限引擎，管理和应用权限策略。"""

    def __init__(self):
        self._strategies: list[AsyncPermissionStrategy[T]] = []
        self.dependencies: set[AclDependency[T]] = set()

    @overload
    def depend(
        self, target_resource_id: str, depend_resource_id: str, /, *, required_mask: Permission = Permission.AVAILABLE
    ):
        """添加 ACL 依赖。该依赖表示执行者自己在 target_resource_id 上的权限
            还取决于自己在 depend_resource_id 上是否拥有 required_mask 权限。

        Args:
            target_resource_id (str): 目标资源 ID。
            depend_resource_id (str): 依赖资源 ID。
            required_mask (Permission): 依赖所需的权限掩码。
        """

    @overload
    def depend(
        self,
        target_subject: User | Role | Callable[[T | None, User | Role], Awaitable[bool]],
        target_resource_id: str,
        depend_resource_id: str,
        /,
        *,
        required_mask: Permission = Permission.AVAILABLE,
    ):
        """添加 ACL 依赖。该依赖表示 target_subject 在 target_resource_id 上的权限
            还取决于 target_subject 在 depend_resource_id 上是否拥有 required_mask 权限。

        Args:
            target_subject (User | Role | Callable[[T | None, User | Role], Awaitable[bool]]): 目标主体或目标检查函数。
            target_resource_id (str): 目标资源 ID。
            depend_resource_id (str): 依赖资源 ID。
            required_mask (Permission): 依赖所需的权限掩码。
        """

    @overload
    def depend(
        self,
        target_resource_id: str,
        dep_subject: User | Role | Callable[[T | None, User | Role], Awaitable[User | Role]],
        depend_resource_id: str,
        /,
        *,
        required_mask: Permission = Permission.AVAILABLE,
    ):
        """添加 ACL 依赖。该依赖表示执行者自己在 target_resource_id 上的权限
            还取决于 dep_subject 在 depend_resource_id 上是否拥有 required_mask 权限。

        Args:
            target_resource_id (str): 目标资源 ID。
            dep_subject (User | Role | Callable[[T, User | Role], Awaitable[User | Role]]): 依赖主体或主体获取函数。
            depend_resource_id (str): 依赖资源 ID。
            required_mask (Permission): 依赖所需的权限掩码。
        """

    @overload
    def depend(
        self,
        target_subject: User | Role | Callable[[T | None, User | Role], Awaitable[bool]],
        target_resource_id: str,
        dep_subject: User | Role | Callable[[T | None, User | Role], Awaitable[User | Role]],
        depend_resource_id: str,
        /,
        *,
        required_mask: Permission = Permission.AVAILABLE,
    ):
        """添加 ACL 依赖。该依赖表示 target_subject 在 target_resource_id 上的权限
            还取决于 dep_subject 在 depend_resource_id 上是否拥有 required_mask 权限。

        Args:
            target_subject (User | Role | Callable[[T | None, User | Role], Awaitable[bool]]): 目标主体或目标检查函数。
            target_resource_id (str): 目标资源 ID。
            dep_subject (User | Role | Callable[[T, User | Role], Awaitable[User | Role]]): 依赖主体或主体获取函数。
            depend_resource_id (str): 依赖资源 ID。
            required_mask (Permission): 依赖所需的权限掩码。
        """

    def depend(
        self,
        *args,
        required_mask: Permission = Permission.AVAILABLE,
    ):
        if len(args) < 2:
            raise ValueError("At least target_resource_id and depend_resource_id are required.")
        if len(args) == 2:
            target_subject = None
            target_resource_id, depend_resource_id = args
            dep_subject = None
        elif len(args) == 3:
            if isinstance(args[1], str):
                target_subject, target_resource_id, depend_resource_id = args
                dep_subject = None
            else:
                target_subject = None
                target_resource_id, dep_subject, depend_resource_id = args
        elif len(args) == 4:
            target_subject, target_resource_id, dep_subject, depend_resource_id = args
        else:
            raise ValueError("Too many positional arguments.")
        self.dependencies.add(
            AclDependency(
                target_resource_id=target_resource_id,
                depend_resource_id=depend_resource_id,
                target_subject=target_subject,
                depend_subject=dep_subject,
                required_mask=required_mask,
            )
        )

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
