from __future__ import annotations

from typing import Optional, Protocol, Sequence

from .ctx import Context
from .node import NodeState


class Owner(Protocol):
    name: str
    priority: Optional[int]
    inherits: list[Owner]
    nodes: dict[str, dict[Context, NodeState]]


def iter_inherits(inherits: Sequence[Owner]):
    for owner in inherits:
        if owner.inherits:
            yield from iter_inherits(owner.inherits)
        yield owner


def export(owner: Owner) -> dict[str, dict[Context, NodeState]]:
    nodes = {}
    inherits: list[Owner] = []
    if owner.inherits:
        inherits.extend(iter_inherits(owner.inherits))
    inherits = list(set(inherits))
    inherits.sort(key=lambda x: x.priority or -1, reverse=True)
    inherits.append(owner)
    for ow in inherits:
        for node, data in ow.nodes.items():
            if node not in nodes:
                nodes[node] = data.copy()
            else:
                nodes[node].update(data)
    return nodes
