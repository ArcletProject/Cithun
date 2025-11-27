from typing import Iterable, Callable, Sequence, overload

from .config import Config
from .model import Owner, NodeState


def iter_inherits(inherits: Sequence[Owner]):
    for owner in inherits:
        if owner.inherits:
            yield from iter_inherits(owner.inherits)
        yield owner


class NodeStore:
    NODES: dict[str, set[str]] = {}  # {"foo": {"foo:bar", "foo:baz"}, "foo:bar": {"foo:bar:baz"}, ...}
    NODE_DEPENDS: dict[str, set[str]] = {}


STORE = NodeStore()


def iter_node(node: str):
    yield node
    while (next_idx := node.rfind(Config.NODE_SEPARATOR)) != -1:
        yield node[:next_idx]
        node = node[:next_idx]


def check_wildcard(node: str):
    left, _, right = node.rpartition(Config.NODE_SEPARATOR)
    if right == "*":
        return True, left
    return False, node


@overload
def define(node: str) -> str: ...


@overload
def define(node: Callable[[], Iterable[str]]) -> list[str]: ...


def define(node):
    if isinstance(node, str):
        parts = [*iter_node(node)]
        parts.reverse()
        MAP = STORE.NODES.setdefault(parts[0], set())
        for part in parts[1:]:
            MAP.add(part)
            MAP = STORE.NODES.setdefault(part, set())
        return node
    return list(map(define, node()))


def depend(node: str, *depends: str):
    if any((path := n) not in STORE.NODES for n in (node, *depends)):
        raise ValueError(f"Node {path} not defined")
    STORE.NODE_DEPENDS.setdefault(node, set()).update(depends)


def traversal(base: str):
    if base not in STORE.NODES:
        raise ValueError(f"Node {base} not defined")
    result = []
    for node in STORE.NODES[base]:
        result.append(node)
        result.extend(traversal(node))
    return result


def export(owner: Owner) -> dict[str, NodeState]:
    nodes = {}
    inherits: list[Owner] = []
    if owner.inherits:
        inherits.extend(iter_inherits(owner.inherits))
    inherits = list(set(inherits))
    inherits.sort(key=lambda x: x.priority or -1, reverse=True)
    inherits.append(owner)
    for ow in inherits:
        nodes.update(ow.nodes)

    def _depend_check(dep: str, cache: dict[str, NodeState]):
        if dep in cache:
            return cache[dep]
        if dep not in nodes:
            state = NodeState(Config.DEFAULT_DIR if STORE.NODES[dep] else Config.DEFAULT_FILE)
        else:
            state = nodes[dep]
        if dep in STORE.NODE_DEPENDS:
            for dep_state in map(lambda p: _depend_check(p, cache), STORE.NODE_DEPENDS[dep]):
                state &= dep_state
        cache[dep] = state
        return state

    _cache = {}

    for path in nodes:
        if path in STORE.NODE_DEPENDS:
            for dep_state in map(lambda p: _depend_check(p, _cache), STORE.NODE_DEPENDS[path]):
                nodes[path] &= dep_state
    return nodes
