from __future__ import annotations
import inspect
from typing import overload, Literal
from weakref import WeakKeyDictionary
from dataclasses import dataclass, field

_MAPPING = {"-": 0, "a": 1, "m": 2, "v": 4}


class NodeState:
    AVAILABLE = 1
    """
    若 state 所属的权限节点拥有子节点，则表示对应的权限拥有者默认情况下对该节点的子节点拥有使用权限
    
    若 state 所属的权限节点不拥有子节点，则表示对应的权限拥有者对该节点拥有使用权限，表示对节点对应的实际内容可用
    """

    MODIFY = 2
    """
    若 state 所属的权限节点拥有子节点，则表示对应的权限拥有者可以增加、删除、修改该节点的子节点（无论子节点的权限是怎样的）
    
    若 state 所属的权限节点不拥有子节点，则表示对应的权限拥有者可以修改该节点的内容
    """

    VISIT = 4
    """
    若 state 所属的权限节点拥有子节点，则表示对应的权限拥有者可以访问该节点的子节点
    
    若 state 所属的权限节点不拥有子节点，则表示对应的权限拥有者可以查看节点的状态和内容
    """

    def __init__(self, state: int | str):
        if isinstance(state, str):
            state = sum(_MAPPING[i] for i in state.lower() if i in _MAPPING)
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
    content: dict[str, str] = field(default_factory=dict, compare=False, hash=False)

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
        _in_current_module = inspect.currentframe().f_back.f_globals["__name__"] == __name__  # type: ignore
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
        if self not in NODE_CHILD_MAP:
            return None
        if name in NODE_CHILD_MAP[self]:
            return NODE_CHILD_MAP[self][name]
        if name in {"$self", ".", ""}:
            return self
        return self.parent if name in {"$parent", ".."} else None

    @overload
    def get(self, path: str) -> Node:
        ...

    @overload
    def get(self, path: str, missing_ok: Literal[True]) -> Node | None:
        ...

    @overload
    def get(self, path: str, missing_ok: Literal[False]) -> Node:
        ...

    def get(self, path: str, missing_ok: bool = False) -> Node | None:
        if not path:
            return self
        if "/" not in path:
            if (res := self._get_once(path)) is None and not missing_ok:
                raise KeyError(path)
            return res
        parts = path.split("/")
        if not parts[0]:
            return ROOT.get("/".join(parts[1:]), missing_ok)  # type: ignore
        if (count := parts[0].count(".")) == len(parts[0]) and count > 2:
            parts[0] = "."
        node = self
        for part in parts:
            node = node._get_once(part)
            if node is None:
                if not missing_ok:
                    raise KeyError("/".join(parts[: parts.index(part) + 1]))
                return None
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

    def __truediv__(self, other: str):
        if self.isfile:
            self.isdir = True
            NODE_CHILD_MAP[self] = {}
        return Node.from_path(other, self)


ROOT = Node("", None, True)
NODE_CHILD_MAP[ROOT] = {}
