from __future__ import annotations
from typing import Iterable

from .model import (
    AclDependency,
    AclEntry,
    InheritMode,
    ResourceNode,
    Role,
    SubjectType,
    User,
)

class BaseStore:
    """
    非线程安全，仅演示用。
    """

    def __init__(self):
        self._acl_counter = 0
        self.resources: dict[str, ResourceNode] = {}
        self.users: dict[str, User] = {}
        self.roles: dict[str, Role] = {}
        self.acls: list[AclEntry] = []

    # ---- Resource ----

    def add_resource(self, res: ResourceNode):
        self.resources[res.id] = res

    def get_resource(self, rid: str) -> ResourceNode:
        return self.resources[rid]

    def get_or_create_resource(
        self,
        rid: str,
        name: str | None = None,
        parent_id: str | None = None,
        inherit_mode: InheritMode = InheritMode.MERGE,
        type_: str = "GENERIC",
    ) -> ResourceNode:
        if rid not in self.resources:
            self.resources[rid] = ResourceNode(
                id=rid,
                name=name or rid,
                parent_id=parent_id,
                inherit_mode=inherit_mode,
                type=type_,
            )
        return self.resources[rid]

    def get_resource_chain(self, rid: str) -> list[ResourceNode]:
        """从当前节点到根节点的链 [current, parent, ..., root]"""
        chain = []
        current = self.resources.get(rid)
        while current:
            chain.append(current)
            if not current.parent_id:
                break
            current = self.resources.get(current.parent_id)
        return chain

    def define(
        self,
        path: str,
        inherit_mode: InheritMode = InheritMode.MERGE,
        type_: str = "GENERIC",
    ) -> ResourceNode:
        parts = [p for p in path.strip("/").split("/") if p]
        if not parts:
            raise ValueError("path must not be empty")

        current_parent_id: str | None = None
        for i, part in enumerate(parts):
            current_id = f"{current_parent_id}/{part}" if current_parent_id else part
            is_last = (i == len(parts) - 1)
            
            if current_id not in self.resources:
                self.resources[current_id] = ResourceNode(
                    id=current_id,
                    name=part,
                    parent_id=current_parent_id,
                    inherit_mode=inherit_mode if is_last else InheritMode.MERGE,
                    type=type_ if is_last else "DIR",
                )
            current_parent_id = current_id
            
        return self.resources[current_parent_id] # type: ignore

    def assign(
        self,
        subject: User | Role,
        resource_path: str,
        allow_mask: int,
        deny_mask: int = 0,
        acl_id: str | None = None,
    ) -> AclEntry:
        subject_id = subject.id
        subject_type = SubjectType.USER if isinstance(subject, User) else SubjectType.ROLE
        res = self.define(resource_path)
        if acl_id is None:
            self._acl_counter += 1
            acl_id = f"acl_{subject_type.value.lower()}_{subject_id}_{res.id}_{self._acl_counter}"

        acl = AclEntry(
            id=acl_id,
            subject_type=subject_type,
            subject_id=subject_id,
            resource_id=res.id,
            allow_mask=allow_mask,
            deny_mask=deny_mask,
        )
        self.add_acl(acl)
        return acl

    def depend(
        self,
        target_acl: AclEntry,
        dep_subject: User | Role,
        dep_resource_path: str,
        required_mask: int,
    ) -> AclEntry:
        dep_subject_id = dep_subject.id
        dep_subject_type = SubjectType.USER if isinstance(dep_subject, User) else SubjectType.ROLE
        dep_res = self.define(dep_resource_path)
        dep = AclDependency(
            subject_type=dep_subject_type,
            subject_id=dep_subject_id,
            resource_id=dep_res.id,
            required_mask=required_mask,
        )
        target_acl.dependencies.append(dep)
        return target_acl
    
    def _ensure_user(self, user: User) -> User:
        if user.id in self.users:
            return user
        self.add_user(user)
        return user

    def _ensure_role(self, role: Role) -> Role:
        if role.id in self.roles:
            return role
        self.add_role(role)
        return role

    def inherit(self, child: User | Role, parent: User | Role):
        if isinstance(child, Role) and isinstance(parent, Role):
            child_role = self._ensure_role(child)
            self._ensure_role(parent)
            if parent.id not in child_role.parent_role_ids:
                child_role.parent_role_ids.append(parent.id)

        elif isinstance(child, User) and isinstance(parent, Role):
            user = self._ensure_user(child)
            self._ensure_role(parent)
            if parent.id not in user.role_ids:
                user.role_ids.append(parent.id)

        elif isinstance(child, User) and isinstance(parent, User):
            user_child = self._ensure_user(child)
            self._ensure_user(parent)
            if parent.id not in user_child.role_ids:
                user_child.role_ids.append(parent.id)
        else:
            raise ValueError("Inherit relationship must be between User-User, User-Role, or Role-Role.")

    # ---- User / Role ----
    def add_user(self, user: User):
        self.users[user.id] = user
        return user

    def add_role(self, role: Role):
        self.roles[role.id] = role
        return role

    def get_user(self, uid: str) -> User:
        return self.users[uid]

    def get_role(self, rid: str) -> Role:
        return self.roles[rid]

    # ---- ACL ----
    def add_acl(self, acl: AclEntry):
        self.acls.append(acl)

    def get_acl(self, subject: User | Role, resource_id: str) -> list[AclEntry]:
        subject_id = subject.id
        subject_type = SubjectType.USER if isinstance(subject, User) else SubjectType.ROLE
        return [
            acl for acl in self.acls
            if acl.subject_type == subject_type and
               acl.subject_id == subject_id and
               acl.resource_id == resource_id
        ]

    def iter_acls_for_resource(self, resource_id: str) -> Iterable[AclEntry]:
        return (acl for acl in self.acls if acl.resource_id == resource_id)
