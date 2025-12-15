from __future__ import annotations

from typing import Generic, TypeVar

from arclet.cithun.model import AclEntry, InheritMode, ResourceNode, Role, SubjectType, User

from .store import AsyncStore
from .strategy import AsyncPermissionEngine

T = TypeVar("T")


class DependencyCycleError(RuntimeError):
    def __init__(self, cycle_nodes: list[tuple[str, str, str]]):
        self.cycle_nodes = cycle_nodes
        msg = "Dependency cycle detected: " + " -> ".join(f"{t}:{sid}@{rid}" for (t, sid, rid) in cycle_nodes)
        super().__init__(msg)


def expand_roles(role_ids: list[str], roles: dict[str, Role]) -> set[str]:
    """递归展开角色列表，获取所有继承的角色 ID。

    Args:
        role_ids (list[str]): 初始角色 ID 列表。
        roles (dict[str, Role]): 角色字典，用于查找角色信息。

    Returns:
        set[str]: 包含所有继承角色的 ID 集合。
    """
    result: set[str] = set()
    visited: set[str] = set()

    def dfs(rid: str):
        if rid in visited:
            return
        visited.add(rid)

        role = roles.get(rid)
        if not role:
            return

        result.add(rid)
        for pr in role.parent_role_ids:
            dfs(pr)

    for rid in role_ids:
        dfs(rid)
    return result


class AsyncPermissionService(Generic[T]):
    def __init__(self, storage: AsyncStore, engine: AsyncPermissionEngine[T]):
        self.storage = storage
        self.engine = engine

    async def get_effective_permissions(
        self,
        user: str | User,
        resource_id: str,
        context: T | None = None,
    ) -> int:
        """计算用户在指定资源上的有效权限。

        Args:
            user (str | User): 用户 ID 或用户对象。
            resource_id (str): 资源 ID。
            context (T | None, optional): 上下文信息。默认为 None。

        Returns:
            int: 有效权限掩码。
        """
        resource = await self.storage.get_resource(resource_id)
        user_id = user.id if isinstance(user, User) else user
        cache: dict[tuple[str, str, str], int] = {}

        async def permission_lookup(subject: User | Role, ctx: T | None) -> int:
            return await self._calc_permissions_for_subject(
                subject.type, subject.id, resource, ctx, visited=[], cache=cache
            )

        base_mask = await self._calc_permissions_for_subject(
            SubjectType.USER, user_id, resource, context, visited=[], cache=cache
        )

        return await self.engine.apply_strategies(
            await self.storage.get_user(user_id),
            resource,
            context,
            base_mask,
            permission_lookup,
        )

    async def has_permission(
        self,
        user: str | User,
        resource_id: str,
        required_mask: int,
        context: T | None = None,
    ) -> bool:
        """检查用户是否拥有指定资源的特定权限。

        Args:
            user (str | User): 用户 ID 或用户对象。
            resource_id (str): 资源 ID。
            required_mask (int): 需要的权限掩码。
            context (T | None, optional): 上下文信息。默认为 None。

        Returns:
            bool: 如果拥有所有请求的权限则返回 True，否则返回 False。
        """
        eff = await self.get_effective_permissions(user, resource_id, context)
        return (eff & required_mask) == required_mask

    async def _calc_permissions_for_subject(
        self,
        subject_type: SubjectType,
        subject: str | User | Role,
        resource: ResourceNode,
        context: T | None,
        visited: list[tuple[str, str, str]],
        cache: dict[tuple[str, str, str], int],
    ) -> int:
        subject_id = subject.id if isinstance(subject, (User, Role)) else subject
        key = (subject_type.value, subject_id, resource.id)
        if key in cache:
            return cache[key]
        if key in visited:
            cycle_start = visited.index(key)
            cycle = visited[cycle_start:] + [key]
            raise DependencyCycleError(cycle)
        visited.append(key)

        chain = list(reversed(await self.storage.get_resource_chain(resource.id)))
        effective_mask = 0

        # Determine relevant subjects (self + inherited roles)
        relevant_subjects: set[tuple[SubjectType, str]] = set()

        if subject_type == SubjectType.USER:
            user = await self.storage.get_user(subject_id)
            relevant_subjects.add((SubjectType.USER, user.id))
            for rid in expand_roles(user.role_ids, self.storage.roles):
                relevant_subjects.add((SubjectType.ROLE, rid))
        else:
            for rid in expand_roles([subject_id], self.storage.roles):
                relevant_subjects.add((SubjectType.ROLE, rid))

        for node in chain:
            node_allow = 0
            node_deny = 0

            for acl in await self.storage.iter_acls_for_resource(node.id):
                if (acl.subject_type, acl.subject_id) not in relevant_subjects:
                    continue

                if not await self._check_acl_dependencies(acl, context, visited, cache):
                    continue

                node_allow |= acl.allow_mask
                node_deny |= acl.deny_mask

            if node.inherit_mode == InheritMode.MERGE:
                effective_mask |= node_allow
            elif node.inherit_mode == InheritMode.OVERRIDE:
                effective_mask = node_allow
            # INHERIT does nothing (keeps previous effective_mask)

            if node_deny:
                effective_mask &= ~node_deny

        cache[key] = effective_mask
        visited.pop()
        return effective_mask

    async def _check_acl_dependencies(
        self,
        acl: AclEntry,
        context: T | None,
        visited: list[tuple[str, str, str]],
        cache: dict[tuple[str, str, str], int],
    ) -> bool:
        if not acl.dependencies:
            return True

        for dep in acl.dependencies:
            dep_res = await self.storage.get_resource(dep.resource_id)
            dep_mask = await self._calc_permissions_for_subject(
                dep.subject_type, dep.subject_id, dep_res, context, visited, cache
            )
            if (dep_mask & dep.required_mask) != dep.required_mask:
                return False
        return True
