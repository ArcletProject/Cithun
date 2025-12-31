from __future__ import annotations

from typing import Generic, TypeVar

from .exceptions import DependencyCycleError
from .model import AclEntry, InheritMode, Permission, ResourceNode, Role, SubjectType, User
from .store import BaseStore
from .strategy import PermissionEngine

T = TypeVar("T")


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


class PermissionService(Generic[T]):
    def __init__(self, storage: BaseStore, engine: PermissionEngine[T]):
        self.storage = storage
        self.engine = engine

    def get_effective_permissions(
        self,
        user: str | User,
        resource_id: str,
        context: T | None = None,
    ) -> Permission:
        """计算用户在指定资源上的有效权限。

        Args:
            user (str | User): 用户 ID 或用户对象。
            resource_id (str): 资源 ID。
            context (T | None, optional): 上下文信息。默认为 None。

        Returns:
            Permission: 有效权限掩码。
        """

        resource = self.storage.get_resource(resource_id)
        user_id = user.id if isinstance(user, User) else user
        cache: dict[tuple[str, str, str], Permission] = {}
        return self._get_effective_permissions_for_subject(SubjectType.USER, user_id, resource, context, visited=[], cache=cache)

    def has_permission(
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
        eff = self.get_effective_permissions(user, resource_id, context)
        return (eff & required_mask) == required_mask

    def _get_effective_permissions_for_subject(
        self,
        subject_type: SubjectType,
        subject_id: str,
        resource: ResourceNode,
        context: T | None,
        visited: list[tuple[str, str, str]],
        cache: dict[tuple[str, str, str], Permission],
    ) -> Permission:
        """
        计算任意 subject（USER/ROLE）在某资源上的最终权限（静态 ACL + 继承 + strategy）。

        注意：
        - 对 USER：策略中传入对应 User 实例。
        - 对 ROLE：策略目前无法直接以 role 为主体，只能按静态 ACL 视角（或者你视业务需要决定要不要对 ROLE 也跑策略）。
        """
        # 1. 静态部分
        base_mask = self._calc_permissions_for_subject(
            subject_type, subject_id, resource, context, visited, cache
        )

        def permission_lookup(subject: User | Role, ctx: T | None) -> Permission:
            return self._calc_permissions_for_subject(subject.type, subject.id, resource, ctx, visited=[], cache=cache)

        # 2. 策略部分
        if subject_type == SubjectType.USER:
            user = self.storage.get_user(subject_id)
            final_mask = self.engine.apply_strategies(
                user,
                resource,
                context,
                base_mask,
                permission_lookup,
            )
            return final_mask

        else:
            return base_mask

    def _calc_permissions_for_subject(
        self,
        subject_type: SubjectType,
        subject: str | User | Role,
        resource: ResourceNode,
        context: T | None,
        visited: list[tuple[str, str, str]],
        cache: dict[tuple[str, str, str], Permission],
    ) -> Permission:
        subject_id = subject.id if isinstance(subject, (User, Role)) else subject
        key = (subject_type.value, subject_id, resource.id)
        if key in cache:
            return cache[key]
        if key in visited:
            cycle_start = visited.index(key)
            cycle = visited[cycle_start:] + [key]
            raise DependencyCycleError(cycle)
        visited.append(key)

        chain = list(reversed(self.storage.get_resource_chain(resource.id)))
        effective_mask = Permission.NONE

        # Determine relevant subjects (self + inherited roles)
        relevant_subjects: set[tuple[SubjectType, str]] = set()

        if subject_type == SubjectType.USER:
            user = self.storage.get_user(subject_id)
            relevant_subjects.add((SubjectType.USER, user.id))
            for rid in expand_roles(user.role_ids, self.storage.roles):
                relevant_subjects.add((SubjectType.ROLE, rid))
        else:
            for rid in expand_roles([subject_id], self.storage.roles):
                relevant_subjects.add((SubjectType.ROLE, rid))

        for node in chain:
            node_allow = Permission.NONE
            node_deny = Permission.NONE

            for acl in self.storage.iter_acls_for_resource(node.id):
                if (acl.subject_type, acl.subject_id) not in relevant_subjects:
                    continue

                if not self._check_acl_dependencies(acl, context, visited, cache):
                    self._check_acl_dependencies(acl, context, visited, cache)
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

    def _check_acl_dependencies(
        self,
        acl: AclEntry,
        context: T | None,
        visited: list[tuple[str, str, str]],
        cache: dict[tuple[str, str, str], Permission],
    ) -> bool:
        if not acl.dependencies:
            return True

        for dep in acl.dependencies:
            dep_res = self.storage.get_resource(dep.resource_id)
            dep_mask = self._get_effective_permissions_for_subject(
                dep.subject_type, dep.subject_id, dep_res, context, visited, cache
            )
            if (dep_mask & dep.required_mask) != dep.required_mask:
                return False
        return True

    def permission_on(
        self,
        subject: User | Role,
        expand_inherited: bool = False,
        show_dependencies: bool = False,
        show_mode: bool = False,
        context: T | None = None,
    ) -> str:
        """生成指定主体在所有资源上的权限视图。

        Args:
            subject (User | Role): 目标主体。
            expand_inherited (bool, optional): 是否展示“展开继承后”的最终权限。默认为 False。
            show_dependencies (bool, optional): 是否显示 ACL 依赖。默认为 False。
            show_mode (bool, optional): 是否显示资源继承模式。默认为 False。
            context (T, optional): 权限计算上下文。expand_inherited=True 时使用。

        Returns:
            str: 权限视图字符串。
        """

        # lines: list[str] = [f"Permission view for {subject.type.value}:{subject.id}"]
        # if expand_inherited:
        #     lines.append("(with inheritance & dependencies)")
        # else:
        #     lines.append("(static ACL entries only)")

        # 为方便展示，按资源树的结构来打印
        lines = ["$"]

        # 预先构建 parent -> children 映射，保证稳定顺序
        children_map: dict[str | None, list[ResourceNode]] = {}
        for res in self.storage.resources.values():
            children_map.setdefault(res.parent_id, []).append(res)

        def _format_node(node: ResourceNode, prefix: str, is_last: bool):
            # 当前资源行前缀
            branch = "└─ " if is_last else "├─ "
            # 找出在该资源上、属于 subject 的 ACL
            acl = self.storage.get_primary_acl(subject, node.id)

            # 基本资源信息
            # 例如: ├─ app/  [mode=MERGE, type=DIR]
            suffix = f" [mode: {node.inherit_mode.value}]" if show_mode else ""

            # 展开后的“最终权限”
            final_perm_str = ""
            if expand_inherited and isinstance(subject, User):
                # 对 User：直接用 get_effective_permissions
                eff = self.get_effective_permissions(subject.id, node.id, context)
                final_perm_str = f":'{eff:#}'" if eff else ""
            elif expand_inherited and isinstance(subject, Role):
                # 对 Role：使用内部 subject 视角计算（只看这个角色及其继承）
                cache: dict[tuple[str, str, str], Permission] = {}
                eff = self._calc_permissions_for_subject(
                    SubjectType.ROLE,
                    subject.id,
                    node,
                    context,
                    visited=[],
                    cache=cache,
                )
                final_perm_str = f":'{eff:#}'" if eff else ""

            # 构造当前节点标题行
            children = children_map.get(node.id, [])
            name_display = node.name + ("/" if children else "")
            line = f"{prefix}{branch}{name_display} {final_perm_str}"

            if acl:
                line += f" (allow: '{acl.allow_mask:#}', deny: '{f'{acl.deny_mask:#}' if acl.deny_mask else 'NONE'}')"
            line += suffix
            lines.append(line)
            if show_dependencies and acl and acl.dependencies:
                for index, dep in enumerate(acl.dependencies):
                    dep_line = (
                        f"{prefix}{'   '}{'└' if index == len(acl.dependencies) - 1 else '├'}"
                        f">{f' {dep.subject_type.value}:{dep.subject_id}  @' if dep.subject_id != subject.type and dep.subject_id != subject.id else ''}"  # noqa: E501
                        f" {dep.resource_id} >= '{dep.required_mask:#}'"
                    )
                    lines.append(dep_line)
            # 递归打印子节点
            for i, child in enumerate(children):
                _format_node(
                    child,
                    prefix + ("   " if is_last else "│  "),
                    i == len(children) - 1,
                )

        # 找出根节点
        roots = children_map.get(None, [])
        for i, root in enumerate(roots):
            _format_node(root, "", i == len(roots) - 1)

        return "\n".join(lines)
