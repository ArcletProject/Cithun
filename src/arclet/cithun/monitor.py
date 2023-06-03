from __future__ import annotations

from collections import ChainMap
from .node import Node, NodeState, ROOT, NODE_CHILD_MAP
from .owner import Owner, Group, User
from .context import Context


def _get(owner: Owner, node: Node, context: Context):
    return next(
        (
            state
            for ctx, state in owner.nodes[node].items()
            if ctx.satisfied(context, "all")
        ),
        None,
    )


def suget(
    owner: Owner, node: Node | str, context: Context | None = None
) -> NodeState | None:
    """得到具体节点的状态，不做权限判断"""
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    if _node not in owner.nodes:
        return
    return _get(owner, _node, context or Context())


def suadd(
    owner: Owner,
    node: Node | str,
    state: NodeState | None = None,
    context: Context | None = None,
):
    """添加节点，不做权限判断"""
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    _ctx = context or Context()
    _prev = _node
    while _prev.parent:
        if _prev.parent not in owner.nodes:
            owner.nodes[_prev.parent] = {_ctx: NodeState(7)}
        if not _get(owner, _prev.parent, _ctx):
            owner.nodes[_prev.parent][_ctx] = NodeState(7)
        _prev = _prev.parent
    if _node in owner.nodes and _get(owner, _node, _ctx):
        raise ValueError(f"node {_node} already exists")
    _node.isdir = not _node.isdir
    if _node in owner.nodes and _get(owner, _node, _ctx):
        raise ValueError(f"node {_node} already exists")
    _node.isdir = not _node.isdir
    owner.nodes.setdefault(_node, {}).setdefault(
        _ctx, state or (NodeState(7) if _node.isdir else NodeState(6))
    )


def suset(
    owner: Owner, node: Node | str, state: NodeState, context: Context | None = None
):
    """设置具体节点的状态，不做权限判断"""
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    _ctx = context or Context()
    if _node not in owner.nodes:
        _node.isdir = not _node.isdir
    if _node not in owner.nodes:
        raise ValueError(f"node {_node} not exists")
    owner.nodes[_node][_ctx] = state


def sudelete(owner: Owner, node: Node | str, context: Context | None = None):
    """删除节点，不做权限判断"""
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    _ctx = context or Context()
    if _node not in owner.nodes:
        _node.isdir = not _node.isdir
    if _node not in owner.nodes:
        return
    owner.nodes[_node].pop(_ctx)
    if not owner.nodes[_node]:
        owner.nodes.pop(_node)
    if _node.isdir:
        for child in NODE_CHILD_MAP[_node].values():
            sudelete(owner, child, _ctx)


def get(
    owner: Owner, node: Node | str, context: Context | None = None
) -> NodeState | None:
    """获取节点状态

    当上层节点的权限不包含v+a时，该节点的状态不可获取

    若节点自己的权限不包含v时，该节点的状态不可获取
    """
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    _ctx = context or Context()
    _prev = _node
    while _prev.parent:
        if _prev.parent in owner.nodes and (
            (res := _get(owner, _prev.parent, _ctx)) and res.state & 5 != 5
        ):
            return
        _prev = _prev.parent
    if _node not in owner.nodes:
        raise ValueError(f"node {_node} not exists")
    res = _get(owner, _node, context or Context())
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
    _ctx = context or Context()
    _prev = _node
    while _prev.parent:
        if _prev.parent not in owner.nodes:
            owner.nodes[_prev.parent] = {_ctx: NodeState(7)}
        if not (res := _get(owner, _prev.parent, _ctx)):
            owner.nodes[_prev.parent][_ctx] = NodeState(7)
        elif res.state & 7 != 7:
            return False
        _prev = _prev.parent
    if _node in owner.nodes and _get(owner, _node, _ctx):
        raise ValueError(f"node {_node} already exists")
    _node.isdir = not _node.isdir
    if _node in owner.nodes and _get(owner, _node, _ctx):
        raise ValueError(f"node {_node} already exists")
    _node.isdir = not _node.isdir
    owner.nodes.setdefault(_node, {}).setdefault(
        _ctx, state or (NodeState(7) if _node.isdir else NodeState(6))
    )
    return True


def set(
    owner: Owner, node: Node | str, state: NodeState, context: Context | None = None
):
    """设置具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    _ctx = context or Context()
    _prev = _node
    while _prev.parent:
        if _prev.parent in owner.nodes and (
            (res := _get(owner, _prev.parent, _ctx)) and res.state & 7 != 7
        ):
            return False
        _prev = _prev.parent
    if _node not in owner.nodes:
        _node.isdir = not _node.isdir
    if _node not in owner.nodes:
        raise ValueError(f"node {_node} not exists")
    res = _get(owner, _node, context or Context())
    if not res:
        raise ValueError(f"node {_node} not exists in context {_ctx}")
    if res.state & 2 == 2:
        owner.nodes[_node][_ctx] = state
        return True
    return False


def delete(owner: Owner, node: Node | str, context: Context | None = None):
    """删除具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
    _node = node if isinstance(node, Node) else ROOT.from_path(node)
    _ctx = context or Context()
    _prev = _node
    while _prev.parent:
        if _prev.parent in owner.nodes and (
            (res := _get(owner, _prev.parent, _ctx)) and res.state & 7 != 7
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
            sudelete(owner, child, _ctx)
        return True
    return False


def available(
    owner: Owner, node: Node | str, context: Context | None = None
) -> bool | None:
    """查看具体节点的状态，若该节点的父节点不可用，则不会返回该节点的状态"""
    res = suget(owner, node, context)
    if res is None:
        return
    return res.state & 1 == 1
