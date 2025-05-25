from __future__ import annotations

from typing import Literal, Tuple, overload

from .config import Config
from .model import NodeState, Owner
from .monitor import BaseMonitor

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


def _check(path: str, nodes: dict[str, NodeState], expect: NodeState, wildcards: set[str]):
    if path not in nodes:
        if intersect := (wildcards & set(BaseMonitor.iter_node(path))):
            path = intersect.pop()
        else:
            return (NodeState(Config.DEFAULT_DIR) & expect) == expect
    state = nodes[path]
    return (state & expect) == expect


class PermissionExecutor:
    def __init__(self, executor: Owner, monitor: BaseMonitor):
        self.executor = executor
        self.monitor = monitor

    def _check_self(self, node: str, expected: Tuple[NodeState, NodeState]):
        _executor_nodes = self.monitor.export(self.executor)

        for parent in self.monitor.iter_node(node):
            if parent == node:
                continue
            if not _check(parent, _executor_nodes, expected[0], self.executor.wildcards):
                return False
        return _check(node, _executor_nodes, expected[1], self.executor.wildcards)

    @overload
    def get(self, target: Owner, node: str) -> NodeState: ...

    @overload
    def get(self, target: Owner, node: str, missing_ok: Literal[True] = True) -> NodeState | None: ...

    def get(self, target: Owner, node: str, missing_ok: bool = False):
        """获取节点状态

        Args:
            target (Owner): 目标对象
            node (str): 目标节点
            missing_ok (bool, optional): 是否允许不存在. Defaults to False.
        """
        if node not in self.monitor.NODES:
            if missing_ok:
                return
            raise FileNotFoundError(f"node {node} not exists")
        if not self._check_self(node, (NodeState("v-a"), NodeState("v--"))):
            raise PermissionError(f"permission denied for {self.executor} to access {node}")
        _nodes = self.monitor.export(target)
        if node not in _nodes:
            if intersect := (target.wildcards & set(self.monitor.iter_node(node))):
                node = intersect.pop()
            else:
                return NodeState(Config.DEFAULT_DIR if self.monitor.NODES[node] else Config.DEFAULT_FILE)
        state = _nodes[node]
        return state

    def set(
        self,
        target: Owner,
        node: str,
        state: NodeState,
        missing_ok: bool = False,
        recursive: bool = False,
    ):
        """设置节点状态

        Args:
            target (Owner): 目标对象
            node (str): 目标节点
            state (NodeState): 目标状态
            missing_ok (bool, optional): 是否允许不存在. Defaults to False.
            recursive (bool, optional): 是否递归. Defaults to False.
        """
        is_wildcard, node = self.monitor.check_wildcard(node)
        if is_wildcard:
            target.wildcards.add(node)
        recursive = is_wildcard or recursive
        if node not in self.monitor.NODES:
            if missing_ok:
                return
            raise FileNotFoundError(f"node {node} not exists")
        if not self._check_self(node, (NodeState("vma"), NodeState("-m-"))):
            raise PermissionError(f"permission denied for {self.executor} to modify {target}'s permission")
        target.nodes[node] = state
        if recursive and self.monitor.NODES[node]:
            for sub_node in self.monitor.NODES[node]:
                self.root(self.monitor).set(target, sub_node, state, missing_ok, recursive if self.monitor.NODES[sub_node] else False)

    def create(self, path: str, parent: bool = True, exist_ok: bool = False):
        """创建节点

        Args:
            path (str): 目标节点
            parent (bool, optional): 是否创建父节点. Defaults to True.
            exist_ok (bool, optional): 是否允许已存在. Defaults to False.
        """
        next(gen := self.monitor.iter_node(path))
        parent_path = next(gen, None)
        if not parent_path:
            if path in self.monitor.NODES:
                if exist_ok:
                    return
                raise FileExistsError(f"node {path} already exists")
            self.monitor.define(path)
            return
        if parent_path not in self.monitor.NODES:
            if parent:
                self.create(parent_path, parent, exist_ok=True)
            else:
                raise FileNotFoundError(f"node {parent_path} not exists")
        if path in self.monitor.NODES:
            if exist_ok:
                return
            raise FileExistsError(f"node {path} already exists")
        if not self._check_self(parent_path, (NodeState("v-a"), NodeState("-m-"))):
            raise PermissionError(f"permission denied for {self.executor} to create {path}")
        self.monitor.define(path)
        return

    @classmethod
    def root(cls, monitor: BaseMonitor):
        """获取根权限执行器

        Args:
            monitor (BaseMonitor): 监视器对象
        """
        return RootPermissionExecutor(monitor)


class RootPermissionExecutor(PermissionExecutor):
    def __init__(self, monitor: BaseMonitor):
        self.monitor = monitor

    def _check_self(self, node: str, expected: Tuple[NodeState, NodeState]):
        return True


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
#   move: 移动权限节点
#       1. 对于原始节点，若其父节点不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       2. 对于原始节点，若其父节点前的父节点的权限不包含 v+a，则抛出异常
#       3. 对于原始节点，若其父节点的权限不包含 v+m+a，则抛出异常
#       4. 对于原始节点，若其自身不存在，则依据参数 `missing_ok: bool` 决定是否抛出异常
#       5. 对于目标节点，若其父节点不存在，则依据参数 `parent: bool` 决定是否创建父节点，否则抛出异常
#       6. 对于目标节点，若其父节点前的父节点的权限不包含 v+a，则抛出异常
#       7. 对于目标节点，若其父节点的权限不包含 v+m+a，则抛出异常
#       8. 对于目标节点，若其自身已存在，则依据参数 `exist_ok: bool` 决定是否抛出异常

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
