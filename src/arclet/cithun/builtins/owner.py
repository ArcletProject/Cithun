from __future__ import annotations

from dataclasses import dataclass, field

from arclet.cithun.node import NodeState


@dataclass(eq=True, unsafe_hash=True)
class DefaultOwner:
    name: str
    priority: int | None = None
    nodes: dict[str, NodeState] = field(default_factory=dict, compare=False, hash=False)
    inherits: list = field(default_factory=list, compare=False, hash=False)
    wildcards: set[str] = field(default_factory=set, compare=False, hash=False)

    def dump(self):
        return {
            "name": self.name,
            "priority": self.priority,
            "nodes": {node: state.state for node, state in self.nodes.items()},
            "inherits": [gp.name for gp in self.inherits],
            "wildcards": list(self.wildcards),
        }

    @classmethod
    def parse(cls, raw: dict):
        obj = cls(raw["name"], raw["priority"], wildcards=set(raw["wildcards"]))
        obj.nodes = {node: NodeState(state) for node, state in raw["nodes"].items()}
        obj.inherits = [DefaultOwner(name, 0) for name in raw["inherits"]]
        return obj

    def __str__(self):
        return f"Owner({self.name})"
