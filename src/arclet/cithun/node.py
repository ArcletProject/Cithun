from __future__ import annotations
import inspect
from typing import overload, TypeVar
from weakref import WeakKeyDictionary
from dataclasses import dataclass

_D = TypeVar("_D")


class NodeState:
    AVAILABLE = 1
    """
    若该节点拥有子节点，则表示该节点的子节点可用
    
    若该节点不拥有子节点，则表示该节点可用，以及节点相关实际内容可用
    """

    MODIFY = 2
    """
    若该节点拥有子节点，则表示该节点拥有者可以为该节点创建，删除，移动子节点
    
    若该节点不拥有子节点，则表示该节点拥有者可以修改节点信息
    """

    VISIT = 4
    """
    若该节点拥有子节点，则表示该节点拥有者可以访问该节点的子节点
    
    若该节点不拥有子节点，则表示该节点拥有者可以访问节点信息
    """

    def __init__(self, state: int | str):
        if isinstance(state, str):
            state = sum({"-": 0, "a": 1, "m": 2, "v": 4}[i] for i in state.lower() if i in {"-", "a", "m", "v"})
        if state < 0 or state > 7:
            raise ValueError("state must be in range [0, 7]")
        self.state = state

    @property
    def available(self):
        return self.state & NodeState.AVAILABLE == NodeState.AVAILABLE

    @property
    def modify(self):
        return self.state & NodeState.MODIFY == NodeState.MODIFY

    @property
    def visit(self):
        return self.state & NodeState.VISIT == NodeState.VISIT

    def __repr__(self):
        state = ["-", "-", "-"]
        if self.available:
            state[2] = "a"
        if self.modify:
            state[1] = "m"
        if self.visit:
            state[0] = "v"
        return "".join(state)


NODE_CHILD_MAP: WeakKeyDictionary['Node', dict[str, 'Node']] = WeakKeyDictionary()


@dataclass(init=False, repr=False, eq=True, unsafe_hash=True)
class Node:
    name: str
    parent: Node | None
    isdir: bool

    @staticmethod
    def from_path(path: str, root: Node | None = None) -> Node:
        _root = root or ROOT
        if _root.isfile:
            raise ValueError("root is a file")
        parts = path.split("/")
        if not parts[0]:
            parts.pop(0)
            _root = ROOT
        elif (count := parts[0].count(".")) == len(parts[0]):
            if count != 2:
                parts.pop(0)
            elif not _root.parent:
                raise ValueError("root has no parent")
            else:
                _root = _root.parent
        end = parts.pop(-1)
        node = _root
        for part in parts:
            node = Node(part, node, True)
        if not end:
            node.isdir = True
            NODE_CHILD_MAP[node] = {}
            return node
        return Node(end, node)

    def __init__(
        self,
        name: str,
        parent: Node | None = None,
        isdir: bool = False,
    ):
        _in_current_module = inspect.currentframe().f_back.f_globals["__name__"] == __name__
        if not _in_current_module and not name:
            raise ValueError("name is required")
        self.name = name
        self.parent = parent if _in_current_module else (parent or ROOT)
        self.isdir = isdir
        if isdir:
            NODE_CHILD_MAP[self] = {}
        if self.parent is not None:
            if self.parent.isfile:
                raise ValueError(f"parent {self.parent} is a file")
            NODE_CHILD_MAP.setdefault(self.parent, {})[self.name] = self

    def move(self, new_parent: Node):
        if new_parent.isfile:
            raise ValueError(f"new parent {new_parent} is a file")
        if self.parent is not None:
            NODE_CHILD_MAP[self.parent].pop(self.name)
        self.parent = new_parent
        NODE_CHILD_MAP[self.parent][self.name] = self

    def _get_once(self, name: str):
        if name in NODE_CHILD_MAP[self]:
            return NODE_CHILD_MAP[self][name]
        if name in {"self", ".", ""}:
            return self
        return self.parent if name in {"parent", ".."} else None

    @overload
    def get(self, path: str) -> Node | None:
        ...

    @overload
    def get(self, path: str, default: _D) -> Node | _D:
        ...

    def get(self, path: str, default: _D = None) -> Node | _D:
        if not path:
            return self
        if "/" not in path:
            return self._get_once(path) or default
        parts = path.split("/")
        if not parts[0]:
            return ROOT.get("/".join(parts[1:]), default)
        if (count := parts[0].count(".")) == len(parts[0]) and count > 2:
            parts[0] = "."
        node = self
        for part in parts:
            node = node._get_once(part)
            if node is None:
                return default
        return node

    def __getitem__(self, name: str):
        if res := self.get(name):
            return res
        raise KeyError(name)

    def __contains__(self, name: str):
        return name in NODE_CHILD_MAP[self]

    def __iter__(self):
        return iter(NODE_CHILD_MAP[self].values())

    def set(self, node: Node):
        node.move(self)

    @property
    def path(self):
        if self.parent is None:
            return "/"
        path = f"'{self.name}'" if " " in self.name else self.name
        node = self
        while node.parent:
            node = node.parent
            path = f"{node.name}/{path}"
        return f"{path}/" if self.isdir else path

    def __repr__(self):
        return f"Node({self.path})"

    @property
    def isfile(self):
        return not self.isdir


ROOT = Node("", None, True)
NODE_CHILD_MAP[ROOT] = {}
