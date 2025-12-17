from __future__ import annotations

import fnmatch
from collections.abc import Callable, Iterable
from itertools import zip_longest
from re import Pattern

from .config import Config
from .model import AclDependency, AclEntry, InheritMode, Permission, ResourceNode, Role, Track, TrackLevel, User


class BaseStore:

    def __init__(self):
        self.resources: dict[str, ResourceNode] = {}
        self.users: dict[str, User] = {}
        self.roles: dict[str, Role] = {}
        self.acls: list[AclEntry] = []
        self.tracks: dict[str, Track] = {}

    def _add_resource(self, res: ResourceNode):
        """添加资源节点。

        Args:
            res (ResourceNode): 资源节点对象。
        """
        self.resources[res.id] = res

    def get_resource(self, rid: str) -> ResourceNode:
        """获取资源节点。

        Args:
            rid (str): 资源 ID。

        Returns:
            ResourceNode: 资源节点对象。
        """
        return self.resources[rid]

    def get_resource_chain(self, rid: str) -> list[ResourceNode]:
        """获取从当前节点到根节点的资源链。

        Args:
            rid (str): 资源 ID。

        Returns:
            list[ResourceNode]: 资源节点列表，顺序为 [current, parent, ..., root]。
        """
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
        """定义资源节点。如果路径上的中间节点不存在，会自动创建为 DIR 类型。

        Args:
            path (str): 资源路径。
            inherit_mode (InheritMode | None, optional): 继承模式。默认为 None。
            type_ (str, optional): 资源类型。默认为 "GENERIC"。

        Returns:
            ResourceNode: 定义的资源节点。

        Raises:
            ValueError: 当 path 为空时抛出。
        """
        parts = [p for p in path.strip(Config.NODE_SEPARATOR).split(Config.NODE_SEPARATOR) if p]
        if not parts:
            raise ValueError("path must not be empty")

        current_parent_id: str | None = None
        node = None

        for i, part in enumerate(parts):
            current_id = f"{current_parent_id}{Config.NODE_SEPARATOR}{part}" if current_parent_id else part
            is_last = i == len(parts) - 1

            node = self.resources.get(current_id)
            if not node:
                node = ResourceNode(
                    id=current_id,
                    name=part,
                    parent_id=current_parent_id,
                    inherit_mode=(inherit_mode or InheritMode.OVERRIDE) if is_last else InheritMode.MERGE,
                    type=type_ if is_last else "DIR",
                )
                self._add_resource(node)
            elif is_last:
                # 已存在，更新属性
                if inherit_mode is not None:
                    node.inherit_mode = inherit_mode
                node.type = type_
            else:
                # 作为中间节点，确保类型为 DIR，继承模式为 MERGE
                node.inherit_mode = InheritMode.MERGE
                node.type = "DIR"
            current_parent_id = current_id

        return node  # type: ignore

    def glob_resources(self, pattern: str) -> list[ResourceNode]:
        """使用 glob 模式匹配资源。

        Args:
            pattern (str): glob 模式字符串。

        Returns:
            list[ResourceNode]: 匹配的资源节点列表。
        """
        pattern = pattern.strip(Config.NODE_SEPARATOR)
        result = []
        for res in self.resources.values():
            rid = res.id.strip(Config.NODE_SEPARATOR)
            if fnmatch.fnmatch(rid, pattern):
                result.append(res)
        return result

    def match_resources(self, pattern: Callable[[str], bool]) -> list[ResourceNode]:
        """使用回调函数匹配资源。

        Args:
            pattern (Callable[[str], bool]): 匹配函数，接受资源 ID 返回布尔值。

        Returns:
            list[ResourceNode]: 匹配的资源节点列表。
        """
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
        allow_mask: Permission,
        deny_mask: Permission = Permission.NONE,
    ) -> None:
        """为指定 subject 在资源上分配 ACL。

        若 resource_path 中包含 '*'，则按 glob 匹配所有已存在资源，对每个资源应用同一个策略；
        否则对单一资源进行操作。

        注意：
        - assign 只会“创建新 ACL”，不会更新已有 ACL；
        - 对已经存在主 ACL 的 subject+resource，应通过 suset/set 来修改。

        Args:
            subject (User | Role): 目标主体。
            resource_path (str | Callable[[str], bool] | Pattern[str]): 资源路径或匹配模式。
            allow_mask (Permission): 允许权限掩码。
            deny_mask (Permission, optional): 拒绝权限掩码。默认为 Permission.None (0)。
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
        required_mask: Permission,
    ) -> AclEntry:
        """添加 ACL 依赖。

        Args:
            target_subject (User | Role): 目标主体。
            target_resource_id (str): 目标资源 ID。
            dep_subject (User | Role): 依赖主体。
            dep_resource_path (str): 依赖资源路径。
            required_mask (Permission): 依赖所需的权限掩码。

        Returns:
            AclEntry: 更新后的目标 ACL 条目。

        Raises:
            ValueError: 当目标 ACL 不存在时抛出。
        """
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

    def inherit(self, child: User | Role, parent: Role):
        """设置继承关系。

        Args:
            child (User | Role): 子主体。
            parent (Role): 父主体。

        Raises:
            ValueError: 当继承关系不合法（如 Role 继承 User）时抛出。
        """
        if isinstance(child, Role):
            child_role = self._ensure_role(child)
            self._ensure_role(parent)
            if parent.id not in child_role.parent_role_ids:
                child_role.parent_role_ids.append(parent.id)
        else:
            user = self._ensure_user(child)
            self._ensure_role(parent)
            if parent.id not in user.role_ids:
                user.role_ids.append(parent.id)

    def create_user(self, uid: str, name: str) -> User:
        """创建用户。

        Args:
            uid (str): 用户 ID。
            name (str): 用户名称。

        Returns:
            User: 创建的用户对象。
        """
        user = User(id=uid, name=name)
        self.users[user.id] = user
        return user

    def create_role(self, rid: str, name: str) -> Role:
        """创建角色。

        Args:
            rid (str): 角色 ID。
            name (str): 角色名称。

        Returns:
            Role: 创建的角色对象。
        """
        role = Role(id=rid, name=name)
        self.roles[role.id] = role
        return role

    def get_user(self, uid: str) -> User:
        """获取用户。

        Args:
            uid (str): 用户 ID。

        Returns:
            User: 用户对象。
        """
        return self.users[uid]

    def get_role(self, rid: str) -> Role:
        """获取角色。

        Args:
            rid (str): 角色 ID。

        Returns:
            Role: 角色对象。
        """
        return self.roles[rid]

    def _add_acl(self, acl: AclEntry):
        self.acls.append(acl)

    def get_acl(self, subject: User | Role, resource_id: str) -> list[AclEntry]:
        """获取指定主体在指定资源上的所有 ACL。

        Args:
            subject (User | Role): 主体。
            resource_id (str): 资源 ID。

        Returns:
            list[AclEntry]: ACL 列表。
        """
        return [
            acl
            for acl in self.acls
            if acl.subject_type == subject.type and acl.subject_id == subject.id and acl.resource_id == resource_id
        ]

    def get_primary_acl(
        self,
        subject: User | Role,
        resource_id: str,
    ) -> AclEntry | None:
        """获取指定主体在指定资源上的主 ACL（第一个匹配的 ACL）。

        Args:
            subject (User | Role): 主体。
            resource_id (str): 资源 ID。

        Returns:
            AclEntry | None: 主 ACL 条目，若不存在则返回 None。
        """
        return next(
            (
                acl
                for acl in self.acls
                if acl.subject_type == subject.type and acl.subject_id == subject.id and acl.resource_id == resource_id
            ),
            None,
        )

    def iter_acls_for_resource(self, resource_id: str) -> Iterable[AclEntry]:
        """迭代指定资源的所有 ACL。

        Args:
            resource_id (str): 资源 ID。

        Returns:
            Iterable[AclEntry]: ACL 迭代器。
        """
        return (acl for acl in self.acls if acl.resource_id == resource_id)

    def create_track(self, tid: str, name: str | None = None) -> Track:
        """创建或获取 Track。

        Args:
            tid (str): Track ID。
            name (str | None, optional): Track 名称。默认为 None。

        Returns:
            Track: Track 对象。
        """
        if tid in self.tracks:
            return self.tracks[tid]
        track = Track(id=tid, name=name or tid)
        self.tracks[track.id] = track
        return track

    def _add_track(self, track: Track):
        """添加 Track。

        Args:
            track (Track): Track 对象。
        """
        self.tracks[track.id] = track

    def get_track(self, tid: str) -> Track:
        """获取 Track。

        Args:
            tid (str): Track ID。

        Returns:
            Track: Track 对象。
        """
        return self.tracks[tid]

    def add_track_level(self, track: Track, role: Role, name: str | None = None) -> None:
        """向 Track 添加一个等级。

        Args:
            track (Track): Track 对象。
            role (Role): 对应的角色。
            name (str | None, optional): 等级名称。默认为 None。
        """
        track.levels.append(
            TrackLevel(
                role_id=role.id,
                level_name=name or role.name,
            )
        )

    def extend_track(self, track: Track, roles: Iterable[Role], names: Iterable[str] | None = None) -> None:
        """批量向 Track 添加等级。

        Args:
            track (Track): Track 对象。
            roles (Iterable[Role]): 角色列表。
            names (Iterable[str] | None, optional): 等级名称列表。默认为 None。
        """
        for role, name in zip_longest(roles, names or []):
            self.add_track_level(track, role, name)

    def insert_track_level(self, track: Track, index: int, role: Role, name: str | None = None) -> None:
        """在指定位置插入 Track 等级。

        Args:
            track (Track): Track 对象。
            index (int): 插入位置索引。
            role (Role): 对应的角色。
            name (str | None, optional): 等级名称。默认为 None。
        """
        track.levels.insert(
            index,
            TrackLevel(
                role_id=role.id,
                level_name=name or role.name,
            ),
        )

    def get_user_track_level(self, user: User, track: Track) -> TrackLevel | None:
        """获取用户在某个 Track 上的当前等级。

        Args:
            user (User): 用户对象。
            track (Track): Track 对象。
        Returns:
            TrackLevel | None: 当前等级对象，若用户不在该 Track 上则返回 None。
        """
        for level in track.levels:
            if level.role_id in user.role_ids:
                return level
        return None

    def set_user_track_level(self, user: User, track: Track, level_index: int) -> None:
        """将用户在某个 Track 上设置到指定等级。

        会清理该用户在该 Track 上已有的其他角色，并赋予新等级对应的角色。

        Args:
            user (User): 用户对象。
            track (Track): Track 对象。
            level_index (int): 目标等级索引。

        Raises:
            ValueError: 当 Track 没有等级或索引无效时抛出。
        """
        levels = track.levels
        if not levels:
            raise ValueError("Track has no levels.")
        if level_index >= len(levels):
            raise ValueError("Invalid level index.")
        track_role_ids = {level.role_id for level in levels}
        user.role_ids = [rid for rid in user.role_ids if rid not in track_role_ids]
        if level_index < 0:
            return
        if levels[level_index].role_id not in user.role_ids:
            user.role_ids.append(levels[level_index].role_id)

    def promote_track(self, user: User, track: Track, step: int = 1):
        """用户在某个 Track 上升级。

        - 当前没有该 Track 角色 -> 为用户挂上最低 level 角色
        - 升级超过最高 level -> 停在最高 level

        Args:
            user (User): 用户对象。
            track (Track): Track 对象。
            step (int, optional): 升级步数。默认为 1。

        Returns:
            int | None: 最终的 level_index。如果 Track 没定义等级则返回 None。
        """
        levels = track.levels
        if not levels:
            return
        current_level_index = -1
        for i, level in enumerate(levels):
            if level.role_id in user.role_ids:
                current_level_index = i
                break

        if current_level_index == -1:
            current_level_index = 0
            self.set_user_track_level(user, track, current_level_index)
            return current_level_index

        new_level_index = min(current_level_index + step, len(levels) - 1)
        self.set_user_track_level(user, track, new_level_index)
        return new_level_index

    def demote_track(self, user: User, track: Track, step: int = 1):
        """用户在某个 Track 上降级。

        - 当前没有该 Track 角色 -> 无视
        - 降级超过最低 level -> 停在最低 level

        Args:
            user (User): 用户对象。
            track (Track): Track 对象。
            step (int, optional): 降级步数。默认为 1。

        Returns:
            int | None: 最终的 level_index。如果 Track 没定义等级或用户不在 Track 中则返回 None。
        """
        levels = track.levels
        if not levels:
            return
        current_level_index = -1
        for i, level in enumerate(levels):
            if level.role_id in user.role_ids:
                current_level_index = i
                break

        if current_level_index == -1:
            return

        new_level_index = max(current_level_index - step, 0)
        self.set_user_track_level(user, track, new_level_index)
        return new_level_index

    def resource_tree(self) -> str:
        """生成资源树的字符串表示。

        Returns:
            str: 资源树字符串。
        """
        lines = ["$"]

        def _format_node(node: ResourceNode, prefix: str, is_last: bool):
            children = [n for n in self.resources.values() if n.parent_id == node.id]
            lines.append(f"{prefix}{'└─ ' if is_last else '├─ '}{node.name}{'/' if children else ''}")
            for i, child in enumerate(children):
                _format_node(child, prefix + ("   " if is_last else "│  "), i == len(children) - 1)

        roots = [n for n in self.resources.values() if n.parent_id is None]
        for i, root in enumerate(roots):
            _format_node(root, "", i == len(roots) - 1)
        return "\n".join(lines)

    def permission_on(self, subject: User | Role):
        """生成指定主体在所有资源上的权限视图。

        Args:
            subject (User | Role): 目标主体。

        Returns:
            str: 权限视图字符串。
        """
        lines = ["$"]

        def _format_node(node: ResourceNode, prefix: str, is_last: bool):
            acl = self.get_primary_acl(subject, node.id)
            if acl:
                perm_str = f"(allow: {acl.allow_mask:#}, deny: {acl.deny_mask:#})"
            else:
                perm_str = ""
            children = [n for n in self.resources.values() if n.parent_id == node.id]
            lines.append(f"{prefix}{'└─ ' if is_last else '├─ '}{node.name}{'/' if children else ''} {perm_str}")
            for i, child in enumerate(children):
                _format_node(child, prefix + ("   " if is_last else "│  "), i == len(children) - 1)

        roots = [n for n in self.resources.values() if n.parent_id is None]
        for i, root in enumerate(roots):
            _format_node(root, "", i == len(roots) - 1)
        return "\n".join(lines)

    def update_acl(self, acl: AclEntry, allow_mask: Permission, deny_mask: Permission | None = None) -> None:
        """更新 ACL 条目。

        Args:
            acl (AclEntry): 要更新的 ACL 条目。
            allow_mask (Permission): 新的允许权限掩码。
            deny_mask (Permission | None, optional): 新的拒绝权限掩码。
        """
        acl.allow_mask = allow_mask
        if deny_mask is not None:
            acl.deny_mask = deny_mask
