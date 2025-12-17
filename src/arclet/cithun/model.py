from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, IntFlag, auto
from typing import ClassVar


class Permission(IntFlag):
    """权限标志位枚举。"""

    NONE = 0
    AVAILABLE = auto()
    MODIFY = auto()
    VISIT = auto()

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            value = value.upper()
            mask = cls.NONE
            for char in value:
                if char == "A" or char == "X":
                    mask |= cls.AVAILABLE
                elif char == "M" or char == "W":
                    mask |= cls.MODIFY
                elif char == "V" or char == "R":
                    mask |= cls.VISIT
                elif char == "*":
                    mask |= cls.AVAILABLE | cls.MODIFY | cls.VISIT
                elif char == "-":
                    continue
                else:
                    raise ValueError(f"Invalid permission character: {char}")
            return cls(mask)
        return super()._missing_(value)

    def __format__(self, format_spec):
        if format_spec == "#":
            flags = []
            for flag, char in (
                (Permission.VISIT, "v"),
                (Permission.MODIFY, "m"),
                (Permission.AVAILABLE, "a"),
            ):
                if self & flag:
                    flags.append(char)
                else:
                    flags.append("-")
            return "".join(flags)
        return super().__format__(format_spec)

    @classmethod
    def parse(cls, expr: str):
        """解析权限表达式为掩码。
        Args:
            expr (str): 权限表达式。形如 [target][op][flags].
        Returns:
            tuple[Permission, str, bool]: (mask, mode, deny)
        """
        expr = expr.strip().lower()
        if not expr:
            raise ValueError("Empty permission expression")
        if len(expr) == 1:
            return cls(int(expr) if expr.isdigit() else expr), "=", False
        mat = re.fullmatch(r"(?P<target>[ad])?(?P<op>[=+-])?(?P<flags>(?:[*0-7]|[vmarwx]+))", expr)
        if not mat:
            raise ValueError(f"Invalid permission expression: {expr!r}")
        deny = (mat.groupdict()["target"] or "a") == "d"
        mode = mat.groupdict()["op"] or "="
        flags_str = mat.groupdict()["flags"]
        return cls(int(flags_str) if flags_str.isdigit() else flags_str), mode, deny


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
    required_mask: Permission


@dataclass
class AclEntry:
    """访问控制列表条目。"""

    subject_type: SubjectType
    subject_id: str
    resource_id: str
    allow_mask: Permission
    deny_mask: Permission = Permission.NONE
    dependencies: list[AclDependency] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"AclEntry(subject={self.subject_type.value}:{self.subject_id}, "
            f"resource={self.resource_id}, allow={self.allow_mask!r}, deny={self.deny_mask!r}, "
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


if __name__ == "__main__":
    print(repr(Permission(7)))
    print(repr(Permission("v-a")))
