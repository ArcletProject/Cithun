from __future__ import annotations

from typing import ClassVar, Literal, Tuple, overload

from .config import Config
from .ctx import Context, Result, Satisfier
from .node import ROOT, Node, NodeState
from .owner import Owner, export

# 分为两类方法：针对权限节点的操作，与针对权限状态的操作
# 权限状态: get, set
#   sget: root 获取执行者权限状态
#       1. 对于目标节点，若其父节点不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常或返回 None
#       2. 对于目标节点，若其自身不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常或返回 None
#   get: 执行者获取目标权限状态
#       1. 对于目标节点，若其父节点不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常或返回 None
#       2. 执行者: 对于目标节点，若其父节点的权限不包含 v+a，则抛出异常
#       3. 对于目标节点，若其自身不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常或返回 None
#       4. 执行者: 对于目标节点，若其自身的权限不包含 v，则抛出异常，否则返回该节点的状态
#   sset: root 设置权限状态
#       1. 对于目标节点，若其父节点不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       2. 对于目标节点，若其自身不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#   set: 执行者设置目标权限状态
#       1. 对于目标节点，若其父节点不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       2. 执行者: 对于目标节点，若其父节点的权限不包含 v+m+a，则抛出异常
#       3. 对于目标节点，若其自身不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       4. 执行者: 对于目标节点，若其自身的权限不包含 m，则不会修改该节点的状态


def _get(nodes: dict[Context, NodeState], context: Context, satisfier: Satisfier):
    return {ctx: state for ctx, state in nodes.items() if satisfier(context, ctx)}


class PermissionExecutor:
    def __init__(self, executor: Owner):
        self.executor = executor

    def _check_self(self, node: Node, expected: Tuple[NodeState, NodeState], context: Context, satisfier: Satisfier):
        _node = node.resolve()
        _executor_nodes = export(self.executor)
        while _node.parent != ROOT:
            node_parent = _node.parent
            if node_parent in _executor_nodes:
                states = _get(_executor_nodes[node_parent], context, satisfier)
                state = max(states.values())
                if state & expected[0] != expected[0]:
                    return False
            elif Config.DEFAULT_DIR & expected[0] != expected[0]:
                return False
            _node = node_parent
        if node in _executor_nodes:
            states = _get(_executor_nodes[node], context, satisfier)
            state = max(states.values())
            if state & expected[1] != expected[1]:
                return False
        elif Config.DEFAULT_DIR & expected[1] != expected[1]:
            return False
        return True

    @overload
    def get(
        self, target: Owner, node: Node | str, context: Context | None = None, satisfier: Satisfier | None = None
    ) -> Result[NodeState]: ...

    @overload
    def get(
        self,
        target: Owner,
        node: Node | str,
        context: Context | None = None,
        satisfier: Satisfier | None = None,
        missing_ok: Literal[True] = True,
    ) -> Result[NodeState] | None: ...

    def get(
        self,
        target: Owner,
        node: Node | str,
        context: Context | None = None,
        satisfier: Satisfier | None = None,
        missing_ok: bool = False,
    ):
        """获取节点状态

        Args:
            target (Owner): 目标对象
            node (Node | str): 目标节点
            context (Context, optional): 上下文. Defaults to None.
            satisfier (Satisfier, optional): 上下文筛选器. Defaults to None.
            missing_ok (bool, optional): 是否允许不存在. Defaults to False.
        """
        _node = node.resolve() if isinstance(node, Node) else Node(node).absolute()
        if not _node.exists():
            if missing_ok:
                return
            raise FileNotFoundError(f"node {_node} not exists")
        _ctx = context or Context.current()
        _satisfier = satisfier or Satisfier.all()
        if not self._check_self(_node, (NodeState("v-a"), NodeState("v--")), _ctx, _satisfier):
            raise PermissionError(f"permission denied for {self.executor} to access {_node}")
        _nodes = export(target)
        if _node not in _nodes:
            return Result({_ctx: Config.DEFAULT_DIR if _node.is_dir() else Config.DEFAULT_FILE}, _ctx)
        if not _ctx.data:
            return Result(_nodes[_node], _ctx)
        return Result(
            _get(_nodes[_node], _ctx, _satisfier)
            or {_ctx: Config.DEFAULT_DIR if _node.is_dir() else Config.DEFAULT_FILE},
            _ctx,
        )

    def set(
        self,
        target: Owner,
        node: Node | str,
        state: NodeState,
        context: Context | None = None,
        satisfier: Satisfier | None = None,
        missing_ok: bool = False,
        recursive: bool = False,
    ):
        """设置节点状态

        Args:
            target (Owner): 目标对象
            node (Node | str): 目标节点
            state (NodeState): 目标状态
            context (Context, optional): 上下文. Defaults to None.
            satisfier (Satisfier, optional): 满足器. Defaults to None.
            missing_ok (bool, optional): 是否允许不存在. Defaults to False.
            recursive (bool, optional): 是否递归. Defaults to False.
        """
        _node = node if isinstance(node, Node) else Node(node).absolute()
        if _node.stem == "*":
            _node = _node.parent
            recursive = True
        if not _node.exists():
            if missing_ok:
                return
            raise FileNotFoundError(f"node {_node} not exists")
        _ctx = context or Context.current()
        _satisfier = satisfier or Satisfier.all()
        if not self._check_self(_node, (NodeState("vma"), NodeState("-m-")), _ctx, _satisfier):
            raise PermissionError(f"permission denied for {self.executor} to modify {target}'s permission")
        target.nodes.setdefault(_node, {})[_ctx] = state
        if recursive:
            for node in _node.iterdir():
                self.root.set(
                    target,
                    node,
                    state,
                    context,
                    satisfier,
                    missing_ok,
                    recursive if node.is_dir() else False
                )

    root: ClassVar["RootPermissionExecutor"]


class RootPermissionExecutor(PermissionExecutor):
    def __init__(self):
        pass

    def _check_self(self, node: Node, expected: Tuple[NodeState, NodeState], context: Context, satisfier: Satisfier):
        return True


PermissionExecutor.root = RootPermissionExecutor()

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
#       3. 对于目标节点，若其父节点的权限不包含 v+m+a，则抛出异常
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
