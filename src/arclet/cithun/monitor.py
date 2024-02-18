from __future__ import annotations

from dataclasses import dataclass, field
from .node import Node, NodeState, ROOT, NODE_CHILD_MAP
from .ctx import Context
from .owner import Owner, Group, User


# 分为两类方法：针对权限节点的操作，与针对权限状态的操作
# 权限状态: get, set, list
#   get: 获取权限状态
#       1. 对于目标节点，若其父节点不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常或返回 None
#       2. 对于目标节点，若其父节点的权限不包含 v+a，则抛出异常
#       3. 对于目标节点，若其自身不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常或返回 None
#       4. 对于目标节点，若其自身的权限不包含 v，则抛出异常，否则返回该节点的状态
#   set: 设置权限状态
#       1. 对于目标节点，若其父节点不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       2. 对于目标节点，若其父节点的权限不包含 v+a，则抛出异常
#       3. 对于目标节点，若其自身不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       4. 对于目标节点，若其自身的权限不包含 m，则不会修改该节点的状态
#   list: 列出所有人的权限状态
#       1. 对于目标节点，若其父节点不存在，则抛出异常
#       2. 对于目标节点，若其父节点的权限不包含 v+a，则抛出异常
#       3. 对于目标节点，若其自身的权限不包含 v，则抛出异常，否则返回该节点的子节点的状态

# 权限节点：create, delete, modify, move, copy, list, require
#   create: 创建权限节点
#       1. 对于目标节点，若其父节点不存在，则依据参数 `parent: bool` 决定是否创建父节点，否则抛出异常
#       2. 对于目标节点，若其父节点前的父节点的权限不包含 v+a，则抛出异常
#       3. 对于目标节点，若其父节点的权限不包含 v+m+a，则抛出异常
#       4. 对于目标节点，若其自身已存在，则依据参数 `exist_ok: bool` 决定是否抛出异常
#   delete: 删除权限节点
#       1. 对于目标节点，若其父节点不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       2. 对于目标节点，若其父节点前的父节点的权限不包含 v+a，则抛出异常
#       3. 对于目标节点，若其父节点的权限不包含 v+m+a，则抛出异常
#       4. 对于目标节点，若其自身不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#   modify: 修改权限节点内容
#       1. 对于目标节点，若其父节点不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       2. 对于目标节点，若其父节点前的父节点的权限不包含 v+a，则抛出异常
#       3. 对于目标节点，若其父节点的权限不包含 v+a，则抛出异常
#       4. 对于目标节点，若其自身不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       5. 对于目标节点，若其自身的权限不包含 m，则抛出异常
#   move: 移动权限节点
#       1. 对于原始节点，若其父节点不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       2. 对于原始节点，若其父节点前的父节点的权限不包含 v+a，则抛出异常
#       3. 对于原始节点，若其父节点的权限不包含 v+m+a，则抛出异常
#       4. 对于原始节点，若其自身不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       5. 对于目标节点，若其父节点不存在，则依据参数 `parent: bool` 决定是否创建父节点，否则抛出异常
#       6. 对于目标节点，若其父节点前的父节点的权限不包含 v+a，则抛出异常
#       7. 对于目标节点，若其父节点的权限不包含 v+m+a，则抛出异常
#       8. 对于目标节点，若其自身已存在，则依据参数 `exist_ok: bool` 决定是否抛出异常
#   copy: 复制权限节点
#       1. 对于原始节点，若其父节点不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       2. 对于原始节点，若其父节点前的父节点的权限不包含 v+a，则抛出异常
#       3. 对于原始节点，若其父节点的权限不包含 v+m+a，则抛出异常
#       4. 对于原始节点，若其自身不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       5. 对于原始节点，若其自身的权限不包含 v，则抛出异常
#       6. 对于目标节点，若其父节点不存在，则依据参数 `parent: bool` 决定是否创建父节点，否则抛出异常
#       7. 对于目标节点，若其父节点前的父节点的权限不包含 v+a，则抛出异常
#       8. 对于目标节点，若其父节点的权限不包含 v+m+a，则抛出异常
#       9. 对于目标节点，若其自身已存在，则依据参数 `exist_ok: bool` 决定是否抛出异常
#   list: 列出权限节点
#       1. 对于目标节点，若其父节点不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       2. 对于目标节点，若其父节点前的父节点的权限不包含 v+a，则抛出异常
#       3. 对于目标节点，若其父节点的权限不包含 v+a，则抛出异常
#       4. 对于目标节点，若其自身的权限不包含 v，则抛出异常，否则返回该节点的子节点的状态
#   require: 判断权限节点是否存在
#       1. 对于目标节点，若其父节点不存在，则返回 False
#       2. 对于目标节点，若其父节点前的父节点的权限不包含 v+a，则返回 `Unknown`
#       3. 对于目标节点，若其父节点的权限不包含 v+a，则返回 `Unknown`
#       4. 对于目标节点，存在则返回 True，否则返回 False


def _get(nodes: dict[Node, dict[Context, NodeState]], node: Node, context: Context):
    return next(
        (state for ctx, state in nodes[node].items() if ctx.satisfied(context, "all")),
        None,
    )


def sget(
    target: Owner, node: Node | str, context: Context | None = None, missing_ok: bool = False
) -> NodeState | None:
    """获取节点状态, 不做权限判断"""
    _node = node if isinstance(node, Node) else ROOT.get(node, missing_ok)
    if _node is None:
        return
    _nodes = target.export()
    if _node not in _nodes:
        return target.DEFAULT
    return _get(_nodes, _node, context or Context.current()) or target.DEFAULT


def sset(
    target: Owner,
    node: Node | str,
    state: NodeState,
    context: Context | None = None,
    missing_ok: bool = False,
):
    """设置节点状态, 不做权限判断"""
    _node = node if isinstance(node, Node) else ROOT.get(node, missing_ok)
    if _node is None:
        return
    _ctx = context or Context.current()
    target.nodes[_node][_ctx] = state

# def sadd(
#     self,
#     node: Node | str,
#     state: NodeState | None = None,
#     context: Context | None = None,
# ):
#     """添加节点，不做权限判断"""
#     _node = node if isinstance(node, Node) else ROOT.from_path(node)
#     _ctx = context or Context.current()
#     _nodes = self._get_nodes()
#     _prev = _node
#     while _prev.parent:
#         if _prev.parent not in _nodes:
#             self.nodes[_prev.parent] = {_ctx: NodeState(7)}
#         elif not _get(_nodes, _prev.parent, _ctx):
#             self.nodes[_prev.parent][_ctx] = NodeState(7)
#         _prev = _prev.parent
#     if _node in _nodes and _get(_nodes, _node, _ctx):
#         raise ValueError(f"node {_node} already exists")
#     _node.isdir = not _node.isdir
#     if _node in _nodes and _get(_nodes, _node, _ctx):
#         raise ValueError(f"node {_node} already exists")
#     _node.isdir = not _node.isdir
#     self.nodes.setdefault(_node, {}).setdefault(
#         _ctx, state or (NodeState(7) if _node.isdir else NodeState(6))
#     )
#
# def smodify(
#     self, node: Node | str, state: NodeState, context: Context | None = None
# ):
#     """设置具体节点的状态，不做权限判断"""
#     _node = node if isinstance(node, Node) else ROOT.from_path(node)
#     _ctx = context or Context.current()
#     if _node not in self.nodes:
#         _node.isdir = not _node.isdir
#     if _node not in self.nodes:
#         raise ValueError(f"node {_node} not exists")
#     self.nodes[_node][_ctx] = state
#
# def sdelete(self, node: Node | str, context: Context | None = None):
#     """删除节点，不做权限判断"""
#     _node = node if isinstance(node, Node) else ROOT.from_path(node)
#     _ctx = context or Context.current()
#     if _node not in self.nodes:
#         _node.isdir = not _node.isdir
#     if _node not in self.nodes:
#         return
#     self.nodes[_node].pop(_ctx)
#     if not self.nodes[_node]:
#         self.nodes.pop(_node)
#     if _node.isdir:
#         for child in NODE_CHILD_MAP[_node].values():
#             self.sdelete(child, _ctx)
#
# def get(self, node: Node | str, context: Context | None = None) -> NodeState | None:
#     """获取节点状态
#
#     当上层节点的权限不包含v+a时，该节点的状态不可获取
#
#     若节点自己的权限不包含v时，该节点的状态不可获取
#     """
#     _node = node if isinstance(node, Node) else ROOT.from_path(node)
#     _ctx = context or Context.current()
#     _nodes = self._get_nodes()
#     _prev = _node
#     while _prev.parent:
#         if _prev.parent in _nodes and (
#             (res := _get(_nodes, _prev.parent, _ctx)) and res.state & 5 != 5
#         ):
#             return
#         _prev = _prev.parent
#     if _node not in _nodes:
#         raise ValueError(f"node {_node} not exists")
#     res = _get(_nodes, _node, context or Context.current())
#     if not res:
#         raise ValueError(f"node {_node} not exists in context {_ctx}")
#     if res.state & 4 == 4:
#         return res
#
# def add(
#     self,
#     node: Node | str,
#     state: NodeState | None = None,
#     context: Context | None = None,
# ):
#     """设置具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
#     _node = node if isinstance(node, Node) else ROOT.from_path(node)
#     _ctx = context or Context.current()
#     _nodes = self._get_nodes()
#     _prev = _node
#     while _prev.parent:
#         if _prev.parent not in _nodes:
#             self.nodes[_prev.parent] = {_ctx: NodeState(7)}
#         elif not (res := _get(_nodes, _prev.parent, _ctx)):
#             self.nodes[_prev.parent][_ctx] = NodeState(7)
#         elif res.state & 7 != 7:
#             return False
#         _prev = _prev.parent
#     if _node in _nodes and _get(_nodes, _node, _ctx):
#         raise ValueError(f"node {_node} already exists")
#     _node.isdir = not _node.isdir
#     if _node in _nodes and _get(_nodes, _node, _ctx):
#         raise ValueError(f"node {_node} already exists")
#     _node.isdir = not _node.isdir
#     self.nodes.setdefault(_node, {}).setdefault(
#         _ctx, state or (NodeState(7) if _node.isdir else NodeState(6))
#     )
#     return True
#
# def modify(
#     self, node: Node | str, state: NodeState, context: Context | None = None
# ):
#     """设置具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
#     _node = node if isinstance(node, Node) else ROOT.from_path(node)
#     _ctx = context or Context.current()
#     _nodes = self._get_nodes()
#     _prev = _node
#     while _prev.parent:
#         if _prev.parent in _nodes and (
#             (res := _get(_nodes, _prev.parent, _ctx)) and res.state & 7 != 7
#         ):
#             return False
#         _prev = _prev.parent
#     if _node not in _nodes:
#         _node.isdir = not _node.isdir
#     if _node not in _nodes:
#         raise ValueError(f"node {_node} not exists")
#     res = _get(_nodes, _node, context or Context.current())
#     if not res:
#         raise ValueError(f"node {_node} not exists in context {_ctx}")
#     if res.state & 2 == 2:
#         self.nodes[_node][_ctx] = state
#         return True
#     return False
#
# def delete(self, node: Node | str, context: Context | None = None):
#     """删除具体节点的状态，若该节点的父节点不可修改，则不会修改该节点的状态"""
#     _node = node if isinstance(node, Node) else ROOT.from_path(node)
#     _ctx = context or Context.current()
#     _prev = _node
#     while _prev.parent:
#         if _prev.parent in self.nodes and (
#             (res := _get(self.nodes, _prev.parent, _ctx)) and res.state & 7 != 7
#         ):
#             return False
#         _prev = _prev.parent
#     if _node not in self.nodes:
#         _node.isdir = not _node.isdir
#     if _node not in self.nodes:
#         raise ValueError(f"node {_node} not exists")
#     if not _node.isdir:
#         self.nodes[_node].pop(_ctx)
#         if not self.nodes[_node]:
#             self.nodes.pop(_node)
#         return True
#     res = self.nodes[_node].get(_ctx)
#     if not res:
#         return ValueError(f"node {_node} not exists in context {_ctx}")
#     if res.state & 2 == 2:
#         self.nodes[_node].pop(_ctx)
#         if not self.nodes[_node]:
#             self.nodes.pop(_node)
#         for child in NODE_CHILD_MAP[_node].values():
#             self.sdelete(child, _ctx)
#         return True
#     return False
#
# def available(
#     self, node: Node | str, context: Context | None = None
# ) -> bool | None:
#     """查看具体节点的状态，若该节点的父节点不可用，则不会返回该节点的状态"""
#     res = self.sget(node, context)
#     if res is None:
#         return
#     return res.state & 1 == 1
#
# def require(
#     self, node: Node | str, context: Context | None = None, missing_ok: bool = True
# ):
#     """查看具体节点的状态，若该节点的父节点不可用，则不会返回该节点的状态
#
#     目标节点不存在且 `missing_ok` 为 True 时，若 Owner 拥有目标节点的任意一父节点的权限，则返回 True
#     """
#     try:
#         state = self.get(node, context)
#     except ValueError:
#         if not missing_ok:
#             return False
#         _node = node if isinstance(node, Node) else ROOT.from_path(node)
#         _ctx = context or Context.current()
#         _prev = _node
#         while _prev.parent:
#             if (res := self.sget(_prev.parent, _ctx)) and res.state & 1 == 1:
#                 return True
#             _prev = _prev.parent
#         return False
#     return False if state is None else state.state & 1 == 1

class Executor:
    def __init__(self, target: Owner):
        self.target = target

    def get(self, operator: Owner):
        ...