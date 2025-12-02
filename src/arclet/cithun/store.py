from __future__ import annotations

from itertools import zip_longest
from collections.abc import Callable
from re import Pattern
from typing import Iterable
import fnmatch

from .model import (
    AclDependency,
    AclEntry,
    InheritMode,
    ResourceNode,
    Role,
    User, Track, TrackLevel,
)
from .config import Config


class BaseStore:
    """
    非线程安全，仅演示用。
    """

    def __init__(self):
        self.resources: dict[str, ResourceNode] = {}
        self.users: dict[str, User] = {}
        self.roles: dict[str, Role] = {}
        self.acls: list[AclEntry] = []
        self.tracks: dict[str, Track] = {}

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
        inherit_mode: InheritMode | None = None,
        type_: str = "GENERIC",
    ) -> ResourceNode:
        parts = [p for p in path.strip(Config.NODE_SEPARATOR).split(Config.NODE_SEPARATOR) if p]
        if not parts:
            raise ValueError("path must not be empty")

        current_parent_id: str | None = None
        for i, part in enumerate(parts):
            current_id = f"{current_parent_id}{Config.NODE_SEPARATOR}{part}" if current_parent_id else part
            is_last = (i == len(parts) - 1)
            
            if current_id not in self.resources:
                self.resources[current_id] = ResourceNode(
                    id=current_id,
                    name=part,
                    parent_id=current_parent_id,
                    inherit_mode=(InheritMode.OVERRIDE if inherit_mode is None else inherit_mode) if is_last else InheritMode.MERGE,
                    type=type_ if is_last else "DIR",
                )
            elif is_last:
                # 已存在，更新属性
                if inherit_mode is not None:
                    self.resources[current_id].inherit_mode = inherit_mode
                self.resources[current_id].type = type_
            else:
                # 作为中间节点，确保类型为 DIR，继承模式为 MERGE
                self.resources[current_id].inherit_mode = InheritMode.MERGE
                self.resources[current_id].type = "DIR"
            current_parent_id = current_id

        return self.resources[current_parent_id]  # type: ignore

    def glob_resources(self, pattern: str) -> list[ResourceNode]:
        """
        简单 glob 匹配资源 id：
        - 支持 '*' 单层匹配（这里直接用 fnmatch.fnmatch 处理，语义与 Unix shell 类似）
        - 仅匹配已存在的资源
        """
        pattern = pattern.strip(Config.NODE_SEPARATOR)
        result = []
        for res in self.resources.values():
            rid = res.id.strip(Config.NODE_SEPARATOR)
            if fnmatch.fnmatch(rid, pattern):
                result.append(res)
        return result

    def match_resources(self, pattern: Callable[[str], bool]) -> list[ResourceNode]:
        result = []
        for res in self.resources.values():
            rid = res.id.strip(Config.NODE_SEPARATOR)
            if pattern(rid):
                result.append(res)
        return result

    def assign(
        self,
        subject: User | Role,
        resource_path: str | Callable[[str], bool] | Pattern[str],
        allow_mask: int,
        deny_mask: int = 0,
    ) -> None:
        """
        为指定 subject 在资源上分配 ACL。

        若 resource_path 中包含 '*'，则按 glob 匹配所有已存在资源，对每个资源应用同一个策略；
        否则对单一资源进行操作。

        注意：
        - assign 只会“创建新 ACL”，不会更新已有 ACL；
        - 对已经存在主 ACL 的 subject+resource，应通过 suset/set 来修改。
        """

        if isinstance(resource_path, str):
            resource_path = resource_path.strip(Config.NODE_SEPARATOR)
            if "*" in resource_path or "?" in resource_path or "[" in resource_path:
                matched = self.glob_resources(resource_path)
            else:
                res = self.define(resource_path)
                acl = AclEntry(
                    subject_type=subject.type,
                    subject_id=subject.id,
                    resource_id=res.id,
                    allow_mask=allow_mask,
                    deny_mask=deny_mask,
                )
                self._add_acl(acl)
                return
        elif isinstance(resource_path, Pattern):
            matched = self.match_resources(lambda t: bool(resource_path.fullmatch(t)))
        else:
            matched = self.match_resources(resource_path)

        for res in matched:
            if self.get_primary_acl(subject, res.id):
                continue
            acl = AclEntry(
                subject_type=subject.type,
                subject_id=subject.id,
                resource_id=res.id,
                allow_mask=allow_mask,
                deny_mask=deny_mask,
            )
            self._add_acl(acl)

    def depend(
        self,
        target_subject: User | Role,
        target_resource_id: str,
        dep_subject: User | Role,
        dep_resource_path: str,
        required_mask: int,
    ) -> AclEntry:
        target_acl = self.get_primary_acl(target_subject, target_resource_id)
        if not target_acl:
            raise ValueError("Target ACL does not exist.")
        dep_res = self.define(dep_resource_path)
        dep = AclDependency(
            subject_type=dep_subject.type,
            subject_id=dep_subject.id,
            resource_id=dep_res.id,
            required_mask=required_mask,
        )
        target_acl.dependencies.append(dep)
        return target_acl
    
    def _ensure_user(self, user: User) -> User:
        if user.id in self.users:
            return user
        self.users[user.id] = user
        return user

    def _ensure_role(self, role: Role) -> Role:
        if role.id in self.roles:
            return role
        self.roles[role.id] = role
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
    def create_user(self, uid: str, name: str) -> User:
        user = User(id=uid, name=name)
        self.users[user.id] = user
        return user

    def create_role(self, rid: str, name: str) -> Role:
        role = Role(id=rid, name=name)
        self.roles[role.id] = role
        return role

    def get_user(self, uid: str) -> User:
        return self.users[uid]

    def get_role(self, rid: str) -> Role:
        return self.roles[rid]

    # ---- ACL ----
    def _add_acl(self, acl: AclEntry):
        self.acls.append(acl)

    def get_acl(self, subject: User | Role, resource_id: str) -> list[AclEntry]:
        return [
            acl for acl in self.acls
            if acl.subject_type == subject.type and
               acl.subject_id == subject.id and
               acl.resource_id == resource_id
        ]

    def get_primary_acl(
        self,
        subject: User | Role,
        resource_id: str,
    ) -> AclEntry | None:
        """
        返回第一个匹配 subject+resource 的 ACL，视为主 ACL。
        若不存在则返回 None。
        """
        return next(
            (
                acl for acl in self.acls
                if acl.subject_type == subject.type
                and acl.subject_id == subject.id
                and acl.resource_id == resource_id
            ),
            None,
        )

    def iter_acls_for_resource(self, resource_id: str) -> Iterable[AclEntry]:
        return (acl for acl in self.acls if acl.resource_id == resource_id)

    def create_track(self, tid: str, name: str | None = None) -> Track:
        if tid in self.tracks:
            return self.tracks[tid]
        track = Track(id=tid, name=name or tid)
        self.tracks[track.id] = track
        return track

    def add_track(self, track: Track):
        self.tracks[track.id] = track

    def get_track(self, tid: str) -> Track:
        return self.tracks[tid]

    def add_track_level(self, track: Track, role: Role, name: str | None = None) -> None:
        level_index = len(track.levels)
        track.levels.append(
            TrackLevel(
                role_id=role.id,
                level_index=level_index,
                level_name=name or role.name,
            )
        )

    def extend_track(self, track: Track, roles: Iterable[Role], names: Iterable[str] | None = None) -> None:
        level_index = len(track.levels)
        for (role, name) in zip_longest(roles, names or []):
            track.levels.append(
                TrackLevel(
                    role_id=role.id,
                    level_index=level_index,
                    level_name=name or role.name,
                )
            )
            level_index += 1

    def insert_track_level(self, track: Track, index: int, role: Role, name: str | None = None) -> None:
        track.levels.insert(
            index,
            TrackLevel(
                role_id=role.id,
                level_index=index,
                level_name=name or role.name,
            )
        )
        # 更新后续 level_index
        for i in range(index + 1, len(track.levels)):
            track.levels[i].level_index = i

    def get_track_levels(self, track: Track) -> list[TrackLevel]:
        return sorted(track.levels, key=lambda l: l.level_index)

    def set_user_track_level(self, user: User, track: Track, level_index: int) -> None:
        """
        把用户在某个 track 上设置到指定等级：
        - 清理该 track 上所有 role
        - 然后为用户挂上“该 track 此 level 对应的 role”
        """
        levels = self.get_track_levels(track)
        if not levels:
            raise ValueError("Track has no levels.")
        if level_index < 0 or level_index >= len(levels):
            raise ValueError("Invalid level index.")
        track_role_ids = {level.role_id for level in levels}
        user.role_ids = [rid for rid in user.role_ids if rid not in track_role_ids]
        if levels[level_index].role_id not in user.role_ids:
            user.role_ids.append(levels[level_index].role_id)

    def promote_track(self, user: User, track: Track, step: int = 1):
        """
        用户在某个 track 上升级 step 级：
        - 当前没有该 track 角色 -> 为用户挂上最低 level 角色
        - 升级超过最高 level -> 停在最高 level
        返回最终的 level_index（或 None 表示 track 没定义）
        """
        levels = self.get_track_levels(track)
        if not levels:
            return
        current_level_index = -1
        for level in levels:
            if level.role_id in user.role_ids:
                current_level_index = level.level_index
                break

        if current_level_index == -1:
            current_level_index = levels[0].level_index
            self.set_user_track_level(user, track, current_level_index)
            return current_level_index

        all_indexes = sorted({level.level_index for level in levels})
        idx_pos = all_indexes.index(current_level_index)
        idx_pos = min(idx_pos + step, len(all_indexes) - 1)
        new_level_index = all_indexes[idx_pos]
        self.set_user_track_level(user, track, new_level_index)
        return new_level_index

    def demote_track(self, user: User, track: Track, step: int = 1):
        """
        用户在某个 track 上降级 step 级：
        - 当前没有该 track 角色 -> 无视
        - 降级超过最低 level -> 停在最低 level
        返回最终的 level_index（或 None 表示 track 没定义）
        """
        levels = self.get_track_levels(track)
        if not levels:
            return
        current_level_index = -1
        for level in levels:
            if level.role_id in user.role_ids:
                current_level_index = level.level_index
                break

        if current_level_index == -1:
            return

        all_indexes = sorted({level.level_index for level in levels})
        idx_pos = all_indexes.index(current_level_index)
        idx_pos = max(idx_pos - step, 0)
        new_level_index = all_indexes[idx_pos]
        self.set_user_track_level(user, track, new_level_index)
        return new_level_index

    def resource_tree(self) -> str:
        lines = ["/"]

        def _format_node(node: ResourceNode, prefix: str, is_last: bool):
            lines.append(f"{prefix}{'└── ' if is_last else '├── '}{node.name} (type={node.type}, inherit_mode={node.inherit_mode})")
            children = [n for n in self.resources.values() if n.parent_id == node.id]
            for i, child in enumerate(children):
                _format_node(child, prefix + ("    " if is_last else "│   "), i == len(children) - 1)
        roots = [n for n in self.resources.values() if n.parent_id is None]
        for i, root in enumerate(roots):
            _format_node(root, "", i == len(roots) - 1)
        return "\n".join(lines)

    def permission_on(self, subject: User | Role):
        lines = ["/"]

        def _format_node(node: ResourceNode, prefix: str, is_last: bool):
            acl = self.get_primary_acl(subject, node.id)
            if acl:
                perm_str = f" allow={acl.allow_mask}, deny={acl.deny_mask}"
            else:
                perm_str = " no ACL"
            lines.append(f"{prefix}{'└── ' if is_last else '├── '}{node.name} (type={node.type}, inherit_mode={node.inherit_mode},{perm_str})")
            children = [n for n in self.resources.values() if n.parent_id == node.id]
            for i, child in enumerate(children):
                _format_node(child, prefix + ("    " if is_last else "│   "), i == len(children) - 1)

        roots = [n for n in self.resources.values() if n.parent_id is None]
        for i, root in enumerate(roots):
            _format_node(root, "", i == len(roots) - 1)
        return "\n".join(lines)
