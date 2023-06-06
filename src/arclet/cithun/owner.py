from __future__ import annotations

from typing import Union
from typing_extensions import TypeAlias
from dataclasses import dataclass, field
from .node import Node, NodeState
from .ctx import Context


@dataclass(eq=True, unsafe_hash=True)
class Group:
    name: str
    priority: int
    nodes: dict[Node, dict[Context, NodeState]] = field(default_factory=dict, compare=False, hash=False)
    inherit: list[Group] = field(default_factory=list, compare=False, hash=False)

    def get_inherits(self):
        for gp in self.inherit:
            if gp.inherit:
                yield from gp.get_inherits()
            yield gp

    def add_inherit(self, *groups: Group):
        for gp in groups:
            if gp not in self.inherit:
                self.inherit.append(gp)


@dataclass
class User:
    name: str
    nodes: dict[Node, dict[Context, NodeState]] = field(default_factory=dict)
    groups: list[Group] = field(default_factory=list)

    def join(self, group: Group):
        if group not in self.groups:
            self.groups.append(group)

    def leave(self, group: Group):
        if group in self.groups:
            self.groups.remove(group)


Owner: TypeAlias = Union[User, Group]
