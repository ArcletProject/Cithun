from __future__ import annotations

from dataclasses import dataclass, field

from arclet.cithun.ctx import Context
from arclet.cithun.node import NodeState


@dataclass(eq=True, unsafe_hash=True)
class DefaultOwner:
    name: str
    priority: int | None = None
    nodes: dict[str, dict[Context, NodeState]] = field(default_factory=dict, compare=False, hash=False)
    inherits: list = field(default_factory=list, compare=False, hash=False)

    def dump(self):
        return {
            "name": self.name,
            "priority": self.priority,
            "nodes": {
                node: {str(ctx): state.state for ctx, state in data.items()} for node, data in self.nodes.items()
            },
            "inherits": [gp.name for gp in self.inherits],
        }

    @classmethod
    def parse(cls, raw: dict):
        obj = cls(raw["name"], raw["priority"])
        obj.nodes = {
            node: {Context.from_string(ctx): NodeState(state) for ctx, state in data.items()}
            for node, data in raw["nodes"].items()
        }
        obj.inherits = [DefaultOwner(name, 0) for name in raw["inherits"]]
        return obj

    def __str__(self):
        return f"Owner({self.name})"
