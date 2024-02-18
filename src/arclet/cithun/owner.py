from __future__ import annotations

from typing import ClassVar
from abc import ABCMeta, abstractmethod
from weakref import WeakValueDictionary
from dataclasses import dataclass, field
from .node import Node, NodeState
from .ctx import Context

USER_TABLE = WeakValueDictionary()
GROUP_TABLE = WeakValueDictionary()


class Owner(metaclass=ABCMeta):
    DEFAULT: ClassVar[NodeState] = NodeState(7)

    inherits: list[Owner]

    def iter_inherits(self):
        for gp in self.inherits:
            if gp.inherits:
                yield from gp.iter_inherits()
            yield gp

    @abstractmethod
    def export(self) -> dict[Node, dict[Context, NodeState]]:
        raise NotImplementedError


@dataclass(eq=True, unsafe_hash=True)
class Group(Owner):
    name: str
    priority: int
    nodes: dict[Node, dict[Context, NodeState]] = field(
        default_factory=dict, compare=False, hash=False
    )
    inherits: list[Group] = field(default_factory=list, compare=False, hash=False)

    def __post_init__(self):
        if self.name in GROUP_TABLE:
            raise ValueError(f"Group {self.name} already exists")
        GROUP_TABLE[self.name] = self

    def inherit(self, *groups: Group):
        for gp in groups:
            if gp not in self.inherits:
                self.inherits.append(gp)

    def export(self):
        nodes = {}
        gps = []
        if self.inherits:
            gps.extend(self.iter_inherits())
        gps.append(self)
        gps.sort(key=lambda x: x.priority, reverse=True)
        for gp in gps:
            for node, data in gp.nodes.items():
                if node not in nodes:
                    nodes[node] = data.copy()
                else:
                    nodes[node].update(data)
        return nodes


@dataclass(eq=True, unsafe_hash=True)
class User(Owner):
    DEFAULT = NodeState(6)

    name: str
    nodes: dict[Node, dict[Context, NodeState]] = field(
        default_factory=dict, compare=False, hash=False
    )
    inherits: list[Group] = field(default_factory=list, compare=False, hash=False)

    def __post_init__(self):
        if self.name in USER_TABLE:
            raise ValueError(f"User {self.name} already exists")
        USER_TABLE[self.name] = self

    def join(self, *groups: Group):
        for gp in groups:
            if gp not in self.inherits:
                self.inherits.append(gp)

    inherit = join

    def leave(self, group: Group):
        if group in self.inherits:
            self.inherits.remove(group)

    def export(self):
        nodes = {}
        gps = []
        for gp in self.inherits:
            if gp.inherits:
                gps.extend(gp.iter_inherits())
            gps.append(gp)
        gps = list(set(gps))
        gps.sort(key=lambda x: x.priority, reverse=True)
        gps.append(self)
        for gp in gps:
            for node, data in gp.nodes.items():
                if node not in nodes:
                    nodes[node] = data.copy()
                else:
                    nodes[node].update(data)
        return nodes
