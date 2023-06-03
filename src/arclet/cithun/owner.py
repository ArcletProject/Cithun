from __future__ import annotations

from typing import Protocol
from dataclasses import dataclass, field
from .node import Node, NodeState
from .context import Context


class Owner(Protocol):
    nodes: dict[Node, dict[Context, NodeState]]


@dataclass(eq=True, unsafe_hash=True)
class Group:
    name: str
    priority: int
    nodes: dict[Node, dict[Context, NodeState]] = field(default_factory=dict, compare=False, hash=False)
    inherit: list[Group] = field(default_factory=list, compare=True, hash=False)

    def get_inherits(self):
        for gp in self.inherit:
            if gp.inherit:
                yield from gp.get_inherits()
            yield gp


@dataclass
class User:
    name: str
    nodes: dict[Node, dict[Context, NodeState]] = field(default_factory=dict)
    groups: list[Group] = field(default_factory=list)
