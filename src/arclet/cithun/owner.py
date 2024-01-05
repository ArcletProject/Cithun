from __future__ import annotations

from dataclasses import dataclass, field
from .node import Node, NodeState
from .ctx import Context


class Owner:
    inherits: list[Owner]

    def iter_inherits(self):
        for gp in self.inherits:
            if gp.inherits:
                yield from gp.iter_inherits()
            yield gp


@dataclass(eq=True, unsafe_hash=True)
class Group(Owner):
    name: str
    priority: int
    nodes: dict[Node, dict[Context, NodeState]] = field(
        default_factory=dict, compare=False, hash=False
    )
    inherits: list[Group] = field(default_factory=list, compare=False, hash=False)

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
    name: str
    nodes: dict[Node, dict[Context, NodeState]] = field(
        default_factory=dict, compare=False, hash=False
    )
    inherits: list[Group] = field(default_factory=list, compare=False, hash=False)

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
