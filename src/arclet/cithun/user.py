from __future__ import annotations

from dataclasses import dataclass, field
from .node import Node, NodeState, ROOT
from .context import Context


@dataclass
class User:
    name: str
    nodes: dict[Node, dict[Context, NodeState]] = field(default_factory=dict)

    def suget(self, node: Node | str, context: Context | None = None) -> NodeState | None:
        """得到具体节点的状态，不做权限判断"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        if _node not in self.nodes:
            return
        _ctx = context or Context()
        return self.nodes[_node].get(_ctx)

    def suadd(self, node: Node | str, state: NodeState | None = None, context: Context | None = None):
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
                raise ValueError(f"node {_node} already exists")
            _node.isdir = not _node.isdir
            self.nodes[_node] = {_ctx: state or (NodeState(7) if _node.isdir else NodeState(6))}

    def suset(self, node: Node | str, state: NodeState | None = None, context: Context | None = None):
        """设置具体节点的状态，不做权限判断"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _ctx = context or Context()
        if _node not in self.nodes:
            _node.isdir = not _node.isdir
        if _node not in self.nodes:
            raise ValueError(f"node {_node} not exists")
        self.nodes[_node][_ctx] = state or (NodeState(7) if _node.isdir else NodeState(6))

    def sudelete(self, node: Node | str, context: Context | None = None):
        """删除具体节点的状态，不做权限判断"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _ctx = context or Context()
        if _node not in self.nodes:
            _node.isdir = not _node.isdir
        if _node not in self.nodes:
            return
        self.nodes[_node].pop(_ctx)
        if not self.nodes[_node]:
            self.nodes.pop(_node)

    def get(self, node: Node | str, context: Context | None = None) -> NodeState | None:
        if not self.visitable(node, context):
            return
        return self.suget(node, context)

    def add(self, node: Node | str, state: NodeState | None = None, context: Context | None = None):
        """设置具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
        return (
            self.suadd(node, state, context)
            if self.modifiable(node, context)
            else False
        )

    def set(self, node: Node | str, state: NodeState | None = None, context: Context | None = None):
        """设置具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
        return (
            self.suset(node, state, context)
            if self.modifiable(node, context)
            else False
        )

    def delete(self, node: Node | str, context: Context | None = None):
        """删除具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
        return (
            self.sudelete(node, context)
            if self.modifiable(node, context)
            else False
        )

    def satisfied(self, node: Node | str, state: int, context: Context | None = None) -> bool | None:
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _ctx = context or Context()
        _prev = _node
        while _prev.parent:
            if (
                _prev.parent in self.nodes
                and _ctx in self.nodes[_prev.parent]
                and self.nodes[_prev.parent][_ctx].state & state != state
            ):
                return False
            _prev = _prev.parent
        if _node not in self.nodes or _ctx not in self.nodes[_node]:
            return
        return self.nodes[_node][_ctx].state & state == state

    def visitable(self, node: Node | str, context: Context | None = None) -> bool | None:
        """查看具体节点的状态，若该节点的父节点不可访问，则不会返回该节点的状态"""
        return self.satisfied(node, 4, context)

    def modifiable(self, node: Node | str, context: Context | None = None) -> bool | None:
        """查看具体节点的状态，若该节点的父节点不可修改，则不会返回该节点的状态"""
        return self.satisfied(node, 2, context)

    def available(self, node: Node | str, context: Context | None = None) -> bool | None:
        """查看具体节点的状态，若该节点的父节点不可用，则不会返回该节点的状态"""
        return self.satisfied(node, 1, context)
