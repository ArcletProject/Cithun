from __future__ import annotations

from dataclasses import dataclass, field
from .node import Node, NodeState, ROOT, NODE_CHILD_MAP
from .ctx import Context


def _get(nodes: dict, node: Node, context: Context):
    return next(
        (state for ctx, state in nodes[node].items() if ctx.satisfied(context, "all")),
        None,
    )


class Owner:
    nodes: dict[Node, dict[Context, NodeState]]
    inherits: list[Owner]

    def iter_inherits(self):
        for gp in self.inherits:
            if gp.inherits:
                yield from gp.iter_inherits()
            yield gp

    def _get_nodes(self):
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

    def sget(
        self, node: Node | str, context: Context | None = None
    ) -> NodeState | None:
        """得到具体节点的状态，不做权限判断"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _nodes = self._get_nodes()
        if _node not in _nodes:
            return
        return _get(_nodes, _node, context or Context.current())

    def sadd(
        self,
        node: Node | str,
        state: NodeState | None = None,
        context: Context | None = None,
    ):
        """添加节点，不做权限判断"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _ctx = context or Context.current()
        _nodes = self._get_nodes()
        _prev = _node
        while _prev.parent:
            if _prev.parent not in _nodes:
                self.nodes[_prev.parent] = {_ctx: NodeState(7)}
            elif not _get(_nodes, _prev.parent, _ctx):
                self.nodes[_prev.parent][_ctx] = NodeState(7)
            _prev = _prev.parent
        if _node in _nodes and _get(_nodes, _node, _ctx):
            raise ValueError(f"node {_node} already exists")
        _node.isdir = not _node.isdir
        if _node in _nodes and _get(_nodes, _node, _ctx):
            raise ValueError(f"node {_node} already exists")
        _node.isdir = not _node.isdir
        self.nodes.setdefault(_node, {}).setdefault(
            _ctx, state or (NodeState(7) if _node.isdir else NodeState(6))
        )

    def smodify(
        self, node: Node | str, state: NodeState, context: Context | None = None
    ):
        """设置具体节点的状态，不做权限判断"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _ctx = context or Context.current()
        if _node not in self.nodes:
            _node.isdir = not _node.isdir
        if _node not in self.nodes:
            raise ValueError(f"node {_node} not exists")
        self.nodes[_node][_ctx] = state

    def sdelete(self, node: Node | str, context: Context | None = None):
        """删除节点，不做权限判断"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _ctx = context or Context.current()
        if _node not in self.nodes:
            _node.isdir = not _node.isdir
        if _node not in self.nodes:
            return
        self.nodes[_node].pop(_ctx)
        if not self.nodes[_node]:
            self.nodes.pop(_node)
        if _node.isdir:
            for child in NODE_CHILD_MAP[_node].values():
                self.sdelete(child, _ctx)

    def get(self, node: Node | str, context: Context | None = None) -> NodeState | None:
        """获取节点状态

        当上层节点的权限不包含v+a时，该节点的状态不可获取

        若节点自己的权限不包含v时，该节点的状态不可获取
        """
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _ctx = context or Context.current()
        _nodes = self._get_nodes()
        _prev = _node
        while _prev.parent:
            if _prev.parent in _nodes and (
                (res := _get(_nodes, _prev.parent, _ctx)) and res.state & 5 != 5
            ):
                return
            _prev = _prev.parent
        if _node not in _nodes:
            raise ValueError(f"node {_node} not exists")
        res = _get(_nodes, _node, context or Context.current())
        if not res:
            raise ValueError(f"node {_node} not exists in context {_ctx}")
        if res.state & 4 == 4:
            return res

    def add(
        self,
        node: Node | str,
        state: NodeState | None = None,
        context: Context | None = None,
    ):
        """设置具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _ctx = context or Context.current()
        _nodes = self._get_nodes()
        _prev = _node
        while _prev.parent:
            if _prev.parent not in _nodes:
                self.nodes[_prev.parent] = {_ctx: NodeState(7)}
            elif not (res := _get(_nodes, _prev.parent, _ctx)):
                self.nodes[_prev.parent][_ctx] = NodeState(7)
            elif res.state & 7 != 7:
                return False
            _prev = _prev.parent
        if _node in _nodes and _get(_nodes, _node, _ctx):
            raise ValueError(f"node {_node} already exists")
        _node.isdir = not _node.isdir
        if _node in _nodes and _get(_nodes, _node, _ctx):
            raise ValueError(f"node {_node} already exists")
        _node.isdir = not _node.isdir
        self.nodes.setdefault(_node, {}).setdefault(
            _ctx, state or (NodeState(7) if _node.isdir else NodeState(6))
        )
        return True

    def modify(
        self, node: Node | str, state: NodeState, context: Context | None = None
    ):
        """设置具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _ctx = context or Context.current()
        _nodes = self._get_nodes()
        _prev = _node
        while _prev.parent:
            if _prev.parent in _nodes and (
                (res := _get(_nodes, _prev.parent, _ctx)) and res.state & 7 != 7
            ):
                return False
            _prev = _prev.parent
        if _node not in _nodes:
            _node.isdir = not _node.isdir
        if _node not in _nodes:
            raise ValueError(f"node {_node} not exists")
        res = _get(_nodes, _node, context or Context.current())
        if not res:
            raise ValueError(f"node {_node} not exists in context {_ctx}")
        if res.state & 2 == 2:
            self.nodes[_node][_ctx] = state
            return True
        return False

    def delete(self, node: Node | str, context: Context | None = None):
        """删除具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
        _node = node if isinstance(node, Node) else ROOT.from_path(node)
        _ctx = context or Context.current()
        _prev = _node
        while _prev.parent:
            if _prev.parent in self.nodes and (
                (res := _get(self.nodes, _prev.parent, _ctx)) and res.state & 7 != 7
            ):
                return False
            _prev = _prev.parent
        if _node not in self.nodes:
            _node.isdir = not _node.isdir
        if _node not in self.nodes:
            raise ValueError(f"node {_node} not exists")
        if not _node.isdir:
            self.nodes[_node].pop(_ctx)
            if not self.nodes[_node]:
                self.nodes.pop(_node)
            return True
        res = self.nodes[_node].get(_ctx)
        if not res:
            return ValueError(f"node {_node} not exists in context {_ctx}")
        if res.state & 2 == 2:
            self.nodes[_node].pop(_ctx)
            if not self.nodes[_node]:
                self.nodes.pop(_node)
            for child in NODE_CHILD_MAP[_node].values():
                self.sdelete(child, _ctx)
            return True
        return False

    def available(
        self, node: Node | str, context: Context | None = None
    ) -> bool | None:
        """查看具体节点的状态，若该节点的父节点不可用，则不会返回该节点的状态"""
        res = self.sget(node, context)
        if res is None:
            return
        return res.state & 1 == 1

    def require(
        self, node: Node | str, context: Context | None = None, missing_ok: bool = True
    ):
        """查看具体节点的状态，若该节点的父节点不可用，则不会返回该节点的状态

        目标节点不存在且 `missing_ok` 为 True 时，若 Owner 拥有目标节点的任意一父节点的权限，则返回 True
        """
        try:
            state = self.get(node, context)
        except ValueError:
            if not missing_ok:
                return False
            _node = node if isinstance(node, Node) else ROOT.from_path(node)
            _ctx = context or Context.current()
            _prev = _node
            while _prev.parent:
                if (res := self.sget(_prev.parent, _ctx)) and res.state & 1 == 1:
                    return True
                _prev = _prev.parent
            return False
        return False if state is None else state.state & 1 == 1


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

    def leave(self, group: Group):
        if group in self.inherits:
            self.inherits.remove(group)

    def _get_nodes(self):
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
