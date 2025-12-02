from __future__ import annotations

from typing import ClassVar
from dataclasses import dataclass, field
from enum import Enum, IntFlag, auto


class Permission(IntFlag):
    NONE = 0
    AVAILABLE = auto()
    MODIFY = auto()
    VISIT = auto()


class InheritMode(str, Enum):
    INHERIT = "INHERIT"    # 完全继承父节点
    MERGE = "MERGE"        # 父 + 子合并
    OVERRIDE = "OVERRIDE"  # 只看当前节点


@dataclass
class ResourceNode:
    id: str
    name: str
    parent_id: str | None = None
    inherit_mode: InheritMode = InheritMode.MERGE
    type: str = "GENERIC"  # FILE / DIR / PROJECT / etc.


class SubjectType(str, Enum):
    USER = "USER"
    ROLE = "ROLE"

@dataclass
class Role:
    id: str
    name: str
    parent_role_ids: list[str] = field(default_factory=list)

    type: ClassVar[SubjectType] = SubjectType.ROLE

@dataclass
class User:
    id: str
    name: str
    role_ids: list[str] = field(default_factory=list)

    type: ClassVar[SubjectType] = SubjectType.USER


@dataclass
class AclDependency:
    """
    描述一个 ACL 对“另一个 subject 在某资源上的权限”的依赖
    """
    subject_type: SubjectType
    subject_id: str
    resource_id: str
    required_mask: int

@dataclass
class AclEntry:
    id: str
    subject_type: SubjectType
    subject_id: str
    resource_id: str
    allow_mask: int
    deny_mask: int = 0
    dependencies: list[AclDependency] = field(default_factory=list)

    def __repr__(self):
        return (
            f"AclEntry(id={self.id}, subject={self.subject_type.value}:{self.subject_id}, "
            f"resource={self.resource_id}, allow={Permission(self.allow_mask)!r}, "
            f"deps={self.dependencies})"
        )
