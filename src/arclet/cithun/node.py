from __future__ import annotations

_MAPPING = {"-": 0, "a": 1, "m": 2, "v": 4}


class NodeState:
    AVAILABLE = 1
    """
    若 state 所属的权限节点拥有子节点，则表示对应的权限拥有者默认情况下对该节点的子节点拥有使用权限
    
    若 state 所属的权限节点不拥有子节点，则表示对应的权限拥有者对该节点拥有使用权限，表示对节点对应的实际内容可用
    """

    MODIFY = 2
    """
    若 state 所属的权限节点拥有子节点，则表示对应的权限拥有者可以修改其他权限拥有者对该权限节点及子节点的权限
    
    若 state 所属的权限节点不拥有子节点，则表示对应的权限拥有者可以修改其他权限拥有者对该权限节点的权限
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

    def __gt__(self, other):
        return self.state > other.state

    def __ge__(self, other):
        return self.state >= other.state

    def __lt__(self, other):
        return self.state < other.state

    def __le__(self, other):
        return self.state <= other.state

    def __eq__(self, other):
        return self.state == other.state

    def __hash__(self):
        return hash(self.state)

    def __bool__(self):
        return bool(self.state)

    def __int__(self):
        return self.state

    def __and__(self, other):
        return NodeState(self.state & other.state)

    def __or__(self, other):
        return NodeState(self.state | other.state)


NODES: dict[str, set] = {}


def ensure_node(node: str):
    parts = [*iter_node(node)]
    parts.reverse()
    MAP = NODES.setdefault(parts[0], set())
    for part in parts[1:]:
        MAP.add(part)
        MAP = NODES.setdefault(part, set())
    return node


def iter_node(node: str):
    yield node
    while (next_idx := node.rfind(".")) != -1:
        yield node[:next_idx]
        node = node[:next_idx]


def check_wildcard(node: str):
    left, _, right = node.rpartition(".")
    if right == "*":
        return True, left
    return False, node


if __name__ == "__main__":
    ensure_node("a.b.c")
    ensure_node("a.e.f")
    print(NODES)
    print(check_wildcard("a.*"))
