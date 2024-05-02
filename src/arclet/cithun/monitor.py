from __future__ import annotations

from dataclasses import dataclass, field

from .ctx import Context
from .node import ROOT, Node, NodeState
from .owner import Group, Owner, User

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


def sget(target: Owner, node: Node | str, context: Context | None = None, missing_ok: bool = False) -> NodeState | None:
    """获取节点状态, 不做权限判断"""
    _node = node if isinstance(node, Node) else Node(node).absolute()
    if not _node.exists():
        if missing_ok:
            return
        raise FileNotFoundError(f"node {_node} not exists")
    _nodes = target.export()
    if _node not in _nodes:
        return target.DEFAULT_DIR if _node.is_dir() else target.DEFAULT_FILE
    return _get(_nodes, _node, context or Context.current()) or target.DEFAULT_DIR if _node.is_dir() else target.DEFAULT_FILE


def sset(
    target: Owner,
    node: Node | str,
    state: NodeState,
    context: Context | None = None,
    missing_ok: bool = False,
):
    """设置节点状态, 不做权限判断"""
    _node = node if isinstance(node, Node) else Node(node).absolute()
    if not _node.exists():
        if missing_ok:
            return
        raise FileNotFoundError(f"node {_node} not exists")
    _ctx = context or Context.current()
    target.nodes.setdefault(_node, {})[_ctx] = state
