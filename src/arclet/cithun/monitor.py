from __future__ import annotations

from .node import Node, NodeState, ROOT, NODE_CHILD_MAP
from .owner import Owner, User
from .ctx import Context


def _get_nodes(owner: Owner):
    nodes = {}
    gps = []
    if isinstance(owner, User):
        for gp in owner.groups:
            if gp.inherit:
                gps.extend(gp.get_inherits())
            gps.append(gp)
        gps = list(set(gps))
        gps.sort(key=lambda x: x.priority, reverse=True)
        gps.append(owner)
    else:
        if owner.inherit:
            gps.extend(owner.get_inherits())
        gps.append(owner)
        gps.sort(key=lambda x: x.priority, reverse=True)
    for gp in gps:
        for node, data in gp.nodes.items():
            if node not in nodes:
                nodes[node] = data.copy()
            else:
                nodes[node].update(data)
    return nodes


def _get(nodes: dict, node: Node, context: Context):
    return next(
        (state for ctx, state in nodes[node].items() if ctx.satisfied(context, "all")),
        None,
    )


def sget(
    owner: Owner, node: Node | str, context: Context | None = None
) -> NodeState | None:
    """得到具体节点的状态，不做权限判断"""
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    _nodes = _get_nodes(owner)
    if _node not in _nodes:
        return
    return _get(_nodes, _node, context or Context.current())


def sadd(
    owner: Owner,
    node: Node | str,
    state: NodeState | None = None,
    context: Context | None = None,
):
    """添加节点，不做权限判断"""
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    _ctx = context or Context.current()
    _nodes = _get_nodes(owner)
    _prev = _node
    while _prev.parent:
        if _prev.parent not in _nodes:
            owner.nodes[_prev.parent] = {_ctx: NodeState(7)}
        elif not _get(_nodes, _prev.parent, _ctx):
            owner.nodes[_prev.parent][_ctx] = NodeState(7)
        _prev = _prev.parent
    if _node in _nodes and _get(_nodes, _node, _ctx):
        raise ValueError(f"node {_node} already exists")
    _node.isdir = not _node.isdir
    if _node in _nodes and _get(_nodes, _node, _ctx):
        raise ValueError(f"node {_node} already exists")
    _node.isdir = not _node.isdir
    owner.nodes.setdefault(_node, {}).setdefault(
        _ctx, state or (NodeState(7) if _node.isdir else NodeState(6))
    )


def smodify(
    owner: Owner, node: Node | str, state: NodeState, context: Context | None = None
):
    """设置具体节点的状态，不做权限判断"""
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    _ctx = context or Context.current()
    if _node not in owner.nodes:
        _node.isdir = not _node.isdir
    if _node not in owner.nodes:
        raise ValueError(f"node {_node} not exists")
    owner.nodes[_node][_ctx] = state


def sdelete(owner: Owner, node: Node | str, context: Context | None = None):
    """删除节点，不做权限判断"""
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    _ctx = context or Context.current()
    if _node not in owner.nodes:
        _node.isdir = not _node.isdir
    if _node not in owner.nodes:
        return
    owner.nodes[_node].pop(_ctx)
    if not owner.nodes[_node]:
        owner.nodes.pop(_node)
    if _node.isdir:
        for child in NODE_CHILD_MAP[_node].values():
            sdelete(owner, child, _ctx)


def get(
    owner: Owner, node: Node | str, context: Context | None = None
) -> NodeState | None:
    """获取节点状态

    当上层节点的权限不包含v+a时，该节点的状态不可获取

    若节点自己的权限不包含v时，该节点的状态不可获取
    """
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    _ctx = context or Context.current()
    _nodes = _get_nodes(owner)
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
    owner: Owner,
    node: Node | str,
    state: NodeState | None = None,
    context: Context | None = None,
):
    """设置具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    _ctx = context or Context.current()
    _nodes = _get_nodes(owner)
    _prev = _node
    while _prev.parent:
        if _prev.parent not in _nodes:
            owner.nodes[_prev.parent] = {_ctx: NodeState(7)}
        elif not (res := _get(_nodes, _prev.parent, _ctx)):
            owner.nodes[_prev.parent][_ctx] = NodeState(7)
        elif res.state & 7 != 7:
            return False
        _prev = _prev.parent
    if _node in _nodes and _get(_nodes, _node, _ctx):
        raise ValueError(f"node {_node} already exists")
    _node.isdir = not _node.isdir
    if _node in _nodes and _get(_nodes, _node, _ctx):
        raise ValueError(f"node {_node} already exists")
    _node.isdir = not _node.isdir
    owner.nodes.setdefault(_node, {}).setdefault(
        _ctx, state or (NodeState(7) if _node.isdir else NodeState(6))
    )
    return True


def modify(
    owner: Owner, node: Node | str, state: NodeState, context: Context | None = None
):
    """设置具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    _ctx = context or Context.current()
    _nodes = _get_nodes(owner)
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
        owner.nodes[_node][_ctx] = state
        return True
    return False


def delete(owner: Owner, node: Node | str, context: Context | None = None):
    """删除具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    _ctx = context or Context.current()
    _prev = _node
    while _prev.parent:
        if _prev.parent in owner.nodes and (
            (res := _get(owner.nodes, _prev.parent, _ctx)) and res.state & 7 != 7
        ):
            return False
        _prev = _prev.parent
    if _node not in owner.nodes:
        _node.isdir = not _node.isdir
    if _node not in owner.nodes:
        raise ValueError(f"node {_node} not exists")
    if not _node.isdir:
        owner.nodes[_node].pop(_ctx)
        if not owner.nodes[_node]:
            owner.nodes.pop(_node)
        return True
    res = owner.nodes[_node].get(_ctx)
    if not res:
        return ValueError(f"node {_node} not exists in context {_ctx}")
    if res.state & 2 == 2:
        owner.nodes[_node].pop(_ctx)
        if not owner.nodes[_node]:
            owner.nodes.pop(_node)
        for child in NODE_CHILD_MAP[_node].values():
            sdelete(owner, child, _ctx)
        return True
    return False


def available(
    owner: Owner, node: Node | str, context: Context | None = None
) -> bool | None:
    """查看具体节点的状态，若该节点的父节点不可用，则不会返回该节点的状态"""
    res = sget(owner, node, context)
    if res is None:
        return
    return res.state & 1 == 1
