from __future__ import annotations

from dataclasses import dataclass, field
from .node import Node, NodeState, ROOT
from .context import Context


@dataclass
class User:
    name: str
    nodes: dict[Node, dict[Context, NodeState]] = field(default_factory=dict)

    def get(self, node: Node | str, context: Context | None = None) -> NodeState | None:
        """得到具体节点的状态，不做权限判断"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        if _node not in self.nodes:
            return
        _ctx = context or Context()
        for ctx, state in self.nodes[_node].items():
            if ctx.satisfied(_ctx):
                return state

    def set(self, node: Node | str, state: NodeState | None = None, context: Context | None = None):
        """设置具体节点的状态，不做权限判断"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _ctx = context or Context()
        _prev = _node
        while _prev.parent:
            if _prev.parent not in self.nodes:
                self.nodes[_prev.parent] = {_ctx: NodeState(7)}
            elif _ctx not in self.nodes[_prev.parent]:
                self.nodes[_prev.parent][_ctx] = NodeState(7)
            _prev = _prev.parent
        if _node not in self.nodes:
            _node.isdir = not _node.isdir
            if _node in self.nodes:
                raise ValueError(f"node {node} already exists")
            _node.isdir = not _node.isdir
            self.nodes[_node] = {}
        self.nodes[_node][_ctx] = state or (NodeState(7) if _node.isdir else NodeState(6))

    def modify(self, node: Node | str, state: NodeState | None = None, context: Context | None = None):
        """设置具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _ctx = context or Context()
        _prev = _node
        while _prev.parent:
            if _prev.parent not in self.nodes:
                self.nodes[_prev.parent] = {_ctx: NodeState(7)}
            elif _ctx not in self.nodes[_prev.parent]:
                self.nodes[_prev.parent][_ctx] = NodeState(7)
            elif not self.nodes[_prev.parent][_ctx].modify:
                return False
            _prev = _prev.parent
        if _node not in self.nodes:
            _node.isdir = not _node.isdir
            if _node in self.nodes:
                raise ValueError(f"node {node} already exists")
            _node.isdir = not _node.isdir
            self.nodes[_node] = {}
        self.nodes[_node][_ctx] = state or (NodeState(7) if _node.isdir else NodeState(6))
        return True

    def visit(self, node: Node | str, context: Context | None = None) -> bool | None:
        """查看具体节点的状态，若该节点的父节点不可访问，则不会返回该节点的状态"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _ctx = context or Context()
        _prev = _node
        while _prev.parent:
            if (
                _prev.parent in self.nodes
                and _ctx in self.nodes[_prev.parent]
                and not self.nodes[_prev.parent][_ctx].visit
            ):
                return False
            _prev = _prev.parent
        if _node not in self.nodes or _ctx not in self.nodes[_node]:
            return
        return self.nodes[_node][_ctx].visit

    def available(self, node: Node | str, context: Context | None = None) -> bool | None:
        """查看节点是否为可用状态，若该节点的父节点不可用，则不会返回该节点的状态"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _ctx = context or Context()
        _prev = _node
        while _prev.parent:
            if (
                _prev.parent in self.nodes
                and _ctx in self.nodes[_prev.parent]
                and not self.nodes[_prev.parent][_ctx].available
            ):
                return False
            _prev = _prev.parent
        if _node not in self.nodes or _ctx not in self.nodes[_node]:
            return
        return self.nodes[_node][_ctx].available
