from __future__ import annotations

from typing import Generic
from typing_extensions import TypeVarTuple, Unpack

from .store import BaseStore
from .model import InheritMode, User, Role, ResourceNode, SubjectType, AclEntry
from .strategy import PermissionEngine


Ts = TypeVarTuple("Ts")


class DependencyCycleError(RuntimeError):
    def __init__(self, cycle_nodes: list[tuple[str, str, str]]):
        self.cycle_nodes = cycle_nodes
        msg = "Dependency cycle detected: " + " -> ".join(
            f"{t}:{sid}@{rid}" for (t, sid, rid) in cycle_nodes
        )
        super().__init__(msg)


def expand_roles(role_ids: list[str], roles: dict[str, Role]) -> set[str]:
    result: set[str] = set()
    visited: set[str] = set()

    def dfs(rid: str):
        if rid in visited:
            return
        visited.add(rid)
        if rid not in roles:
            return
        result.add(rid)
        for pr in roles[rid].parent_role_ids:
            dfs(pr)

    for rid in role_ids:
        dfs(rid)
    return result


class PermissionService(Generic[Unpack[Ts]]):
    def __init__(self, storage: BaseStore, engine: PermissionEngine[Unpack[Ts]]):
        self.storage = storage
        self.engine = engine

    def get_effective_permissions(
        self,
        user: str | User,
        resource_id: str,
        context: tuple[Unpack[Ts]] | None = None,
    ) -> int:
        context = context or tuple()
        resource = self.storage.get_resource(resource_id)
        user_id = user.id if isinstance(user, User) else user
        cache : dict[tuple[str, str, str], int] = {}

        def permission_lookup(subject: User | Role, *ctx: Unpack[Ts]) -> int:
            subject_type = SubjectType.USER if isinstance(subject, User) else SubjectType.ROLE
            return self._calc_permissions_for_subject(subject_type, subject.id, resource, ctx, visited=[], cache=cache)
        base_mask = self._calc_permissions_for_subject(SubjectType.USER, user_id, resource, context, visited=[], cache=cache)

        return self.engine.apply_strategies(
            self.storage.get_user(user_id),
            resource,
            context,
            base_mask,
            permission_lookup,
        )

    def has_permission(
        self,
        user: str | User,
        resource_id: str,
        required_mask: int,
        context: tuple[Unpack[Ts]] | None = None,
    ) -> bool:
        eff = self.get_effective_permissions(user, resource_id, context)
        return (eff & required_mask) == required_mask

    def _calc_permissions_for_subject(
        self,
        subject_type: SubjectType,
        subject: str | User | Role,
        resource: ResourceNode,
        context: tuple[Unpack[Ts]],
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

        chain = list(reversed(self.storage.get_resource_chain(resource.id)))
        effective_mask = 0

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
            node_allow = 0
            node_deny = 0

            for acl in self.storage.iter_acls_for_resource(node.id):
                if (acl.subject_type, acl.subject_id) not in relevant_subjects:
                    continue

                if not self._check_acl_dependencies(acl, context, visited, cache):
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
        context: tuple[Unpack[Ts]],
        visited: list[tuple[str, str, str]],
        cache: dict[tuple[str, str, str], int],
    ) -> bool:
        if not acl.dependencies:
            return True

        for dep in acl.dependencies:
            dep_res = self.storage.get_resource(dep.resource_id)
            dep_mask = self._calc_permissions_for_subject(
                dep.subject_type, dep.subject_id, dep_res, context, visited, cache
            )
            if (dep_mask & dep.required_mask) != dep.required_mask:
                return False
        return True
