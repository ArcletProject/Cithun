from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntFlag, auto
from typing import ClassVar


class Permission(IntFlag):
    """权限标志位枚举。"""

    NONE = 0
    AVAILABLE = auto()
    MODIFY = auto()
    VISIT = auto()


class InheritMode(str, Enum):
    """权限继承模式。"""

    INHERIT = "INHERIT"
    """完全继承父节点"""

    MERGE = "MERGE"
    """父 + 子合并"""

    OVERRIDE = "OVERRIDE"
    """只看当前节点"""


@dataclass
class ResourceNode:
    """资源节点。"""

    id: str
    name: str
    parent_id: str | None = None
    inherit_mode: InheritMode = InheritMode.MERGE
    type: str = "GENERIC"  # FILE / DIR / PROJECT / etc.


class SubjectType(str, Enum):
    """主体类型（用户或角色）。"""

    USER = "USER"
    ROLE = "ROLE"


@dataclass
class Role:
    """角色。"""

    id: str
    name: str
    parent_role_ids: list[str] = field(default_factory=list)

    type: ClassVar[SubjectType] = SubjectType.ROLE


@dataclass
class User:
    """用户。"""

    id: str
    name: str
    role_ids: list[str] = field(default_factory=list)

    type: ClassVar[SubjectType] = SubjectType.USER


@dataclass(eq=True)
class AclDependency:
    """描述一个 ACL 对“另一个 subject 在某资源上的权限”的依赖。"""

    subject_type: SubjectType
    subject_id: str
    resource_id: str
    required_mask: int


@dataclass
class AclEntry:
    """访问控制列表条目。"""

    subject_type: SubjectType
    subject_id: str
    resource_id: str
    allow_mask: int
    deny_mask: int = 0
    dependencies: list[AclDependency] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"AclEntry(subject={self.subject_type.value}:{self.subject_id}, "
            f"resource={self.resource_id}, allow={Permission(self.allow_mask)!r}, "
            f"deps={self.dependencies})"
        )


@dataclass(eq=True)
class TrackLevel:
    """
    Track 中的一个“等级节点”：
    - 对应一个 Role
    - 有一个顺序 level_index（0,1,2,...，index 越大代表等级越高）
    """

    role_id: str
    level_name: str  # 例如：MEMBER, ADMIN, OWNER


@dataclass
class Track:
    """
    一条“轨道”，管理一组有序角色：
    比如：AUTH_1 ~ AUTH_5。
    """

    id: str
    name: str
    levels: list[TrackLevel] = field(default_factory=list)
