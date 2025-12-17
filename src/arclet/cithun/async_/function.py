from __future__ import annotations

from collections.abc import Callable
from re import Pattern
from typing import Generic, TypeVar

from arclet.cithun.config import Config
from arclet.cithun.exceptions import PermissionDeniedError, ResourceNotFoundError
from arclet.cithun.model import Permission, ResourceNode, Role, User

from .service import AsyncPermissionService
from .store import AsyncStore

T = TypeVar("T")


class AsyncPermissionExecutor(Generic[T]):
    """
    专门负责对“权限状态”的 get/set 操作。

    这里的“权限状态”定义为：某个 subject 在某个资源节点上的有效权限 bitmask（int）。

    - suget / suset : 以 root 身份操作（无权限检查）
    - get / set     : 以执行者（某个 User）身份操作，并按题设规则做检查
    """

    def __init__(
        self,
        storage: AsyncStore,
        perm_service: AsyncPermissionService[T],
    ):
        self.storage = storage
        self.service = perm_service

    async def _get_parent_and_self(
        self,
        resource_path: str,
        missing_ok: bool,
    ) -> tuple[ResourceNode | None, ResourceNode | None]:
        """获取父节点和当前节点。

        Args:
            resource_path (str): 资源路径。
            missing_ok (bool): 是否允许节点不存在。

        Returns:
            tuple[ResourceNode | None, ResourceNode | None]: (parent_node, self_node)。

        Raises:
            ResourceNotFoundError: 当 missing_ok=False 且节点不存在时抛出。
        """
        path = resource_path.strip(Config.NODE_SEPARATOR)
        if not path:
            # 根节点没有父节点的概念，这里约定 parent=None, self=root(如果存在)
            # root = self.storage.resources.get("root")
            # if root is None and not missing_ok:
            if missing_ok:
                return None, None
            raise ResourceNotFoundError("Root resource 'root' does not exist")

        # 获取 self
        try:
            self_node = await self.storage.get_resource(resource_path)
        except KeyError:
            self_node = None

        # 获取 parent
        parent_id = None
        if Config.NODE_SEPARATOR in path:
            parent_id, _, _ = path.rpartition(Config.NODE_SEPARATOR)

        try:
            parent_node = await self.storage.get_resource(parent_id) if parent_id else None
        except KeyError:
            parent_node = None

        # 父节点不存在
        if parent_node is None and parent_id and not missing_ok:
            raise ResourceNotFoundError(f"Parent resource '{parent_id}' not found")

        # 自身不存在
        if self_node is None and not missing_ok:
            raise ResourceNotFoundError(f"Resource '{path}' not found")

        return parent_node, self_node

    async def _ensure_resource_for_set(
        self,
        resource_path: str,
        missing_ok: bool,
    ) -> tuple[ResourceNode | None, ResourceNode]:
        """确保资源存在以进行设置操作。

        Args:
            resource_path (str): 资源路径。
            missing_ok (bool): 是否允许自动创建。

        Returns:
            tuple[ResourceNode | None, ResourceNode]: (parent_node, self_node)。

        Raises:
            ResourceNotFoundError: 当 missing_ok=False 且资源不存在时抛出。
        """
        parent, node = await self._get_parent_and_self(resource_path, missing_ok=missing_ok)
        if node is None:
            if not missing_ok:
                raise ResourceNotFoundError(f"Resource '{resource_path}' not found")
            # 自动创建
            node = await self.storage.define(resource_path)
        return parent, node

    def _apply_chmod(
        self,
        old_mask: Permission,
        mask: Permission,
        mode: str,
    ) -> Permission:
        """应用 chmod 风格的权限调整。

        Args:
            old_mask (int): 旧的权限掩码。
            mask (int): 新的权限掩码。
            mode (str): 调整模式。
                "=" : 覆盖为 mask
                "+" : old_mask | mask
                "-" : old_mask & ~mask

        Returns:
            int: 调整后的权限掩码。

        Raises:
            ValueError: 当 mode 不支持时抛出。
        """
        if mode == "=":
            return mask
        elif mode == "+":
            return old_mask | mask
        elif mode == "-":
            return old_mask & ~mask
        else:
            raise ValueError(f"Unsupported chmod mode: {mode!r}")

    async def suget(
        self,
        subject: User | Role,
        resource_path: str,
        missing_ok: bool = False,
        context: T | None = None,
    ) -> Permission | None:
        """root 获取 subject 在指定节点上的权限状态（bitmask），不做权限校验。

        Args:
            subject (User | Role): 目标主体（用户或角色）。
            resource_path (str): 资源路径。
            missing_ok (bool, optional): 是否允许节点不存在。默认为 False。
            context (T | None, optional): 上下文信息。默认为 None。

        Returns:
            Permission | None: 权限掩码。如果 missing_ok=True 且节点不存在，返回 None。

        Raises:
            ResourceNotFoundError: 当 missing_ok=False 且节点不存在时抛出。
        """
        _, node = await self._get_parent_and_self(resource_path, missing_ok=missing_ok)
        # 若 missing_ok=True，则 parent 或 node 可能为 None，此时按规则返回 None
        if node is None:
            return None

        # 直接用内部方法计算该 subject 的静态权限
        if isinstance(subject, Role):
            cache: dict[tuple[str, str, str], Permission] = {}
            mask = await self.service._calc_permissions_for_subject(
                subject.type,
                subject.id,
                node,
                context,
                visited=[],
                cache=cache,
            )
        else:
            mask = await self.service.get_effective_permissions(subject, node.id, context)
        return mask

    async def test(
        self,
        subject: User | Role,
        resource_path: str,
        required_mask: Permission,
        missing_ok: bool = False,
        context: T | None = None,
    ) -> bool:
        """root 测试 subject 在指定节点上是否拥有某些权限，不做权限校验。

        Args:
            subject (User | Role): 目标主体（用户或角色）。
            resource_path (str): 资源路径。
            required_mask (Permission): 需要的权限掩码。
            missing_ok (bool, optional): 是否允许节点不存在。默认为 False。
            context (T | None, optional): 上下文信息。默认为 None。

        Returns:
            bool: 是否拥有指定权限。如果 missing_ok=True 且节点不存在，返回 False。

        Raises:
            ResourceNotFoundError: 当 missing_ok=False 且节点不存在时抛出。
        """
        mask = await self.suget(
            subject,
            resource_path,
            missing_ok=missing_ok,
            context=context,
        )
        if mask is None:
            mask = Permission.VISIT | Permission.AVAILABLE
        return (mask & required_mask) == required_mask

    async def get(
        self,
        executor: User,
        resource_path: str,
        missing_ok: bool = False,
        context: T | None = None,
    ) -> Permission | None:
        """执行者获取自己在目标节点的权限状态。

        Args:
            executor (User): 执行者。
            resource_path (str): 资源路径。
            missing_ok (bool, optional): 是否允许节点不存在。默认为 False。
            context (tuple | None, optional): 上下文信息。默认为 None。

        Returns:
            Permission | None: 权限掩码。如果 missing_ok=True 且节点不存在，返回 None。

        Raises:
            ResourceNotFoundError: 当 missing_ok=False 且节点不存在时抛出。
            PermissionDeniedError: 当执行者在节点缺少 VISIT 权限时抛出
        """
        _, node = await self._get_parent_and_self(resource_path, missing_ok=missing_ok)

        # 3. 自身不存在
        if node is None:
            return None

        # 4. 检查自身权限包含 VISIT
        # 如果某个父节点显式 deny V，这里自然拿不到 V
        self_mask = await self.service.get_effective_permissions(executor, node.id, context)
        if (self_mask & Permission.VISIT) != Permission.VISIT:
            raise PermissionDeniedError(f"Executor '{executor.id}' lacks VISIT on '{node.id}'")
        return self_mask

    async def suset(
        self,
        subject: User | Role,
        resource_path: str | Callable[[str], bool] | Pattern[str],
        mask: Permission,
        mode: str = "=",
        deny: bool = False,
        missing_ok: bool = False,
    ) -> None:
        """root 为 subject 在指定节点上“设置权限状态”。

        Args:
            subject (User | Role): 目标主体（用户或角色）。
            resource_path (str | Callable[[str], bool] | Pattern[str]): 资源路径或匹配模式。
            mask (Permission): 权限掩码。
            mode (str, optional): 设置模式 ("=", "+", "-")。默认为 "="。
            deny (bool, optional): 是否设置为 deny 掩码。默认为 False（设置为 allow）。
            missing_ok (bool, optional): 是否允许节点不存在。默认为 False。

        Raises:
            ResourceNotFoundError: 当 missing_ok=False 且节点不存在时抛出。
            ValueError: 当 mode 不支持时抛出。
        """

        if isinstance(resource_path, str):
            resource_path = resource_path.strip(Config.NODE_SEPARATOR)
            if "*" in resource_path or "?" in resource_path or "[" in resource_path:
                matched = await self.storage.glob_resources(resource_path)
            else:
                _, node = await self._ensure_resource_for_set(resource_path, missing_ok=missing_ok)

                primary_acl = await self.storage.get_primary_acl(subject, node.id)
                old_mask = (
                    (primary_acl.deny_mask if deny else primary_acl.allow_mask) if primary_acl else Permission.NONE
                )
                new_mask = self._apply_chmod(old_mask, mask, mode)
                if primary_acl is None:
                    await self.storage.assign(
                        subject=subject,
                        resource_path=node.id,
                        allow_mask=Permission.NONE if deny else new_mask,
                        deny_mask=new_mask if deny else Permission.NONE,
                    )
                else:
                    await self.storage.update_acl(
                        primary_acl,
                        allow_mask=new_mask if not deny else primary_acl.allow_mask,
                        deny_mask=new_mask if deny else primary_acl.deny_mask,
                    )
                return
        elif isinstance(resource_path, Pattern):
            matched = await self.storage.match_resources(lambda t: bool(resource_path.fullmatch(t)))
        else:
            matched = await self.storage.match_resources(resource_path)
        for node in matched:
            if node.parent_id and node.parent_id not in self.storage.resources:
                if not missing_ok:
                    raise ResourceNotFoundError(f"Parent '{node.parent_id}' for '{node.id}' not found")
                else:
                    continue

            primary_acl = await self.storage.get_primary_acl(subject, node.id)
            old_mask = (primary_acl.deny_mask if deny else primary_acl.allow_mask) if primary_acl else Permission.NONE
            new_mask = self._apply_chmod(old_mask, mask, mode)
            if primary_acl is None:
                await self.storage.assign(
                    subject=subject,
                    resource_path=node.id,
                    allow_mask=Permission.NONE if deny else new_mask,
                    deny_mask=new_mask if deny else Permission.NONE,
                )
            else:
                await self.storage.update_acl(
                    primary_acl,
                    allow_mask=new_mask if not deny else primary_acl.allow_mask,
                    deny_mask=new_mask if deny else primary_acl.deny_mask,
                )

    async def chmod(
        self,
        subject: User | Role,
        resource_path: str | Callable[[str], bool] | Pattern[str],
        pattern: str,
        missing_ok: bool = False,
    ) -> None:
        """root 为 subject 在指定节点上“设置权限状态”。

        Args:
            subject (User | Role): 目标主体（用户或角色）。
            resource_path (str | Callable[[str], bool] | Pattern[str]): 资源路径或匹配模式。
            pattern (str): 权限表达式。形如 [target][op][flags]。
            missing_ok (bool, optional): 是否允许节点不存在。默认为 False。

        Raises:
            ResourceNotFoundError: 当 missing_ok=False 且节点不存在时抛出。
            ValueError: 当 mode 不支持时抛出。
        """
        return await self.suset(subject, resource_path, *Permission.parse(pattern), missing_ok=missing_ok)

    async def set(
        self,
        executor: User,
        target: User | Role,
        resource_path: str | Callable[[str], bool] | Pattern[str],
        mask: Permission,
        mode: str = "=",
        deny: bool = False,
        missing_ok: bool = False,
        context: T | None = None,
    ) -> None:
        """执行者为目标 subject 设置目标节点的权限状态。

        Args:
            executor (User): 执行者。
            target (User | Role): 目标主体（用户或角色）。
            resource_path (str | Callable[[str], bool] | Pattern[str]): 资源路径或匹配模式。
            mask (Permission): 权限掩码。
            mode (str, optional): 设置模式 ("=", "+", "-")。默认为 "="。
            deny (bool, optional): 是否设置为 deny 掩码。默认为 False（设置为 allow）。
            missing_ok (bool, optional): 是否允许节点不存在。默认为 False。
            context (tuple | None, optional): 上下文信息。默认为 None。

        Raises:
            ResourceNotFoundError: 当 missing_ok=False 且节点不存在时抛出。
            PermissionDeniedError: 当执行者权限不足时抛出。
            ValueError: 当 mode 不支持时抛出。
        """
        if isinstance(resource_path, str):
            resource_path = resource_path.strip(Config.NODE_SEPARATOR)
            if "*" in resource_path or "?" in resource_path or "[" in resource_path:
                matched = await self.storage.glob_resources(resource_path)
            else:
                parent, node = await self._ensure_resource_for_set(resource_path, missing_ok=missing_ok)

                # 2. 检查执行者在父节点是否有 v+m+a
                if parent is not None:
                    parent_mask = await self.service.get_effective_permissions(executor, parent.id, context)
                    required_parent = Permission.VISIT | Permission.MODIFY | Permission.AVAILABLE
                    if (parent_mask & required_parent) != required_parent:
                        raise PermissionDeniedError(f"Executor '{executor.id}' lacks V+M+A on parent '{parent.id}'")

                # 4. 检查执行者在自身是否有 MODIFY
                self_mask = await self.service.get_effective_permissions(executor, node.id, context)
                if (self_mask & Permission.MODIFY) != Permission.MODIFY:
                    # 不修改该节点状态
                    return

                primary_acl = await self.storage.get_primary_acl(target, node.id)
                old_mask = (
                    (primary_acl.deny_mask if deny else primary_acl.allow_mask) if primary_acl else Permission.NONE
                )
                new_mask = self._apply_chmod(old_mask, mask, mode)
                if primary_acl is None:
                    await self.storage.assign(
                        subject=target,
                        resource_path=node.id,
                        allow_mask=Permission.NONE if deny else new_mask,
                        deny_mask=new_mask if deny else Permission.NONE,
                    )
                else:
                    await self.storage.update_acl(
                        primary_acl,
                        allow_mask=new_mask if not deny else primary_acl.allow_mask,
                        deny_mask=new_mask if deny else primary_acl.deny_mask,
                    )
                return
        elif isinstance(resource_path, Pattern):
            matched = await self.storage.match_resources(lambda t: bool(resource_path.fullmatch(t)))
        else:
            matched = await self.storage.match_resources(resource_path)
        for node in matched:
            parent = self.storage.resources.get(node.parent_id) if node.parent_id else None
            if node.parent_id and parent is None:
                if not missing_ok:
                    raise ResourceNotFoundError(f"Parent '{node.parent_id}' for '{node.id}' not found")
                else:
                    continue
            if parent is not None:
                parent_mask = await self.service.get_effective_permissions(executor, parent.id, context)
                required_parent = Permission.VISIT | Permission.MODIFY | Permission.AVAILABLE
                if (parent_mask & required_parent) != required_parent:
                    raise PermissionDeniedError(f"Executor '{executor.id}' lacks V+M+A on parent '{parent.id}'")
            self_mask = await self.service.get_effective_permissions(executor, node.id, context)
            if (self_mask & Permission.MODIFY) != Permission.MODIFY:
                continue  # 无修改权限，跳过

            # 5. chmod 更新目标 subject
            primary_acl = await self.storage.get_primary_acl(target, node.id)
            old_mask = (primary_acl.deny_mask if deny else primary_acl.allow_mask) if primary_acl else Permission.NONE
            new_mask = self._apply_chmod(old_mask, mask, mode)
            if primary_acl is None:
                await self.storage.assign(
                    subject=target,
                    resource_path=node.id,
                    allow_mask=Permission.NONE if deny else new_mask,
                    deny_mask=new_mask if deny else Permission.NONE,
                )
            else:
                await self.storage.update_acl(
                    primary_acl,
                    allow_mask=new_mask if not deny else primary_acl.allow_mask,
                    deny_mask=new_mask if deny else primary_acl.deny_mask,
                )
