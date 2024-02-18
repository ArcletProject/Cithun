from __future__ import annotations
import inspect
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


# NODE_CHILD_MAP: WeakKeyDictionary['Node', dict[str, 'Node']] = WeakKeyDictionary()
INDEX_MAP: dict[str, Node] = {}


@dataclass(init=False, repr=False, eq=True, unsafe_hash=True)
class Node:
    name: str
    content: dict[str, str] = field(compare=False, hash=False)

    def __init__(
        self,
        name: str,
        content: dict[str, str] | None = None,
    ):
        _in_current_module = inspect.currentframe().f_back.f_globals["__name__"] == __name__  # type: ignore
        if not _in_current_module and not name:
            raise ValueError("name is required")
        self.name = name
        self.content = content or {}
        # self.name = name
        # self.parent = parent if _in_current_module else (parent or ROOT)
        # self.isdir = isdir
        # if isdir:
        #     NODE_CHILD_MAP[self] = {}
        # if self.parent is not None:
        #     if self.parent.isfile:
        #         raise ValueError(f"parent {self.parent} is a file")
        #     NODE_CHILD_MAP.setdefault(self.parent, {})[self.name] = self

    @property
    def isdir(self):
        return self.content.get("$type") == "dir"

    @property
    def isfile(self):
        return self.content.get("$type") == "file"

    @property
    def path(self):
        return self.content.get("$path", self.name)

    @property
    def parent(self):
        return self.content.get("$parent")

    def exist(self):
        return self.path in INDEX_MAP

    def mkdir(
        self,
        path: str,
        content: dict[str, str] | None = None,
        *,
        exist_ok: bool = False,
        parents: bool = False,
    ):
        return mkdir(path, self, content, exist_ok=exist_ok, parents=parents)

    def touch(
        self,
        path: str,
        content: dict[str, str] | None = None,
        *,
        exist_ok: bool = False,
        parents: bool = False,
    ):
        return touch(path, self, content, exist_ok=exist_ok, parents=parents)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"{'DIR' if self.isdir else 'FILE'}({self.name!r})"


ROOT = Node("/", {"$type": "dir", "$path": ""})


def split_path(path: str, base: Node) -> tuple[Node, list[str]]:
    if not path:
        raise ValueError("path is required")
    if path == "/":
        return ROOT, []
    parts = path.split("/")
    first = parts[0]
    if not first:  # absolute path
        parts.pop(0)
        return ROOT, parts
    if first == ".":  # current node
        return base, parts[1:]
    _base = base
    while first == "..":  # parent node
        parts.pop(0)
        first = parts[0]
        if not _base.parent:
            raise ValueError("base has no parent")
        _base = _base.parent
    return _base, parts


def mkdir(
    path: str,
    base: Node = ROOT,
    content: dict[str, str] | None = None,
    *,
    exist_ok: bool = False,
    parents: bool = False,
):
    if base.isfile:
        raise ValueError("base is a file")
    _base, parts = split_path(path, base)
    if not parts:
        raise ValueError("path is required")
    if len(parts) == 1:
        _path = f"{_base.path}/{parts[0]}"
        if not exist_ok and _path in INDEX_MAP:
            raise FileExistsError(_path)
        node = Node(parts[0], {"$type": "dir", "$path": _path, "$parent": _base, **(content or {})})
        INDEX_MAP[_path] = node
        return node
    if not parents:
        raise FileNotFoundError(parts[0])
    for part in parts[:-1]:
        _path = f"{_base.path}/{part}"
        if not exist_ok and _path in INDEX_MAP:
            raise FileExistsError(_path)
        _base = Node(part, {"$type": "dir", "$path": _path, "$parent": _base})
        INDEX_MAP[_path] = _base
    _path = f"{_base.path}/{parts[-1]}"
    if not exist_ok and _path in INDEX_MAP:
        raise FileExistsError(_path)
    node = Node(parts[-1], {"$type": "dir", "$path": _path, "$parent": _base, **(content or {})})
    INDEX_MAP[_path] = node
    return node


def touch(
    path: str,
    base: Node = ROOT,
    content: dict[str, str] | None = None,
    *,
    exist_ok: bool = False,
    parents: bool = False,
):
    if base.isfile:
        raise ValueError("base is a file")
    _base, parts = split_path(path, base)
    if not parts:
        raise ValueError("path is required")
    if len(parts) == 1:
        _path = f"{_base.path}/{parts[0]}"
        if not exist_ok and _path in INDEX_MAP:
            raise FileExistsError(_path)
        node = Node(parts[0], {"$type": "file", "$path": _path, "$parent": _base, **(content or {})})
        INDEX_MAP[_path] = node
        return node
    if not parents:
        raise FileNotFoundError(parts[0])
    for part in parts[:-1]:
        _path = f"{_base.path}/{part}"
        if not exist_ok and _path in INDEX_MAP:
            raise FileExistsError(_path)
        _base = Node(part, {"$type": "dir", "$path": _path, "$parent": _base})
        INDEX_MAP[_path] = _base
    _path = f"{_base.path}/{parts[-1]}"
    if not exist_ok and _path in INDEX_MAP:
        raise FileExistsError(_path)
    node = Node(parts[-1], {"$type": "file", "$path": _path, "$parent": _base, **(content or {})})
    INDEX_MAP[_path] = node
    return node
