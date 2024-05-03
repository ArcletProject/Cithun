from __future__ import annotations

from typing import Protocol, Sequence, Union

from .ctx import Context
from .node import Node, NodeState

DEFAULT_DIR = NodeState(7)
DEFAULT_FILE = NodeState(6)


class Group(Protocol):
    name: str
    priority: int
    inherits: list[Group]
    nodes: dict[Node, dict[Context, NodeState]]


class User(Protocol):
    name: str
    inherits: list[Group]
    nodes: dict[Node, dict[Context, NodeState]]


Owner = Union[Group, User]


def iter_inherits(inherits: Sequence[Owner]):
    for owner in inherits:
        if owner.inherits:
            yield from iter_inherits(owner.inherits)
        yield owner


def export(owner: Owner) -> dict[Node, dict[Context, NodeState]]:
    nodes = {}
    gps = []
    if owner.inherits:
        gps.extend(iter_inherits(owner.inherits))
    gps = list(set(gps))
    gps.sort(key=lambda x: x.priority, reverse=True)
    gps.append(owner)
    for gp in gps:
        for node, data in gp.nodes.items():
            if node not in nodes:
                nodes[node] = data.copy()
            else:
                nodes[node].update(data)
    return nodes
