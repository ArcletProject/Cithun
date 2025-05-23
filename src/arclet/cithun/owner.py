from __future__ import annotations

from typing import Optional, Protocol, Sequence

from .state import NodeState


class Owner(Protocol):
    name: str
    priority: Optional[int]
    inherits: list[Owner]
    nodes: dict[str, NodeState]
    wildcards: set[str]
