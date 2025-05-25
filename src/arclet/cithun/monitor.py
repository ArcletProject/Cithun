import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable
from typing import Iterable, Optional, Generic, Callable, Sequence, overload, Union
from typing_extensions import TypeVarTuple, Unpack

from .config import Config
from .model import Owner, NodeState


Ts = TypeVarTuple("Ts")


def iter_inherits(inherits: Sequence[Owner]):
    for owner in inherits:
        if owner.inherits:
            yield from iter_inherits(owner.inherits)
        yield owner


class BaseMonitor:
    NODES: dict[str, set[str]]
    NODE_DEPENDS: dict[str, set[str]]

    @staticmethod
    def iter_node(node: str):
        yield node
        while (next_idx := node.rfind(Config.NODE_SEPARATOR)) != -1:
            yield node[:next_idx]
            node = node[:next_idx]

    @staticmethod
    def check_wildcard(node: str):
        left, _, right = node.rpartition(Config.NODE_SEPARATOR)
        if right == "*":
            return True, left
        return False, node

    @overload
    def define(self, node: str) -> str: ...

    @overload
    def define(self, node: Callable[[], Iterable[str]]) -> list[str]: ...

    def define(self, node):
        if isinstance(node, str):
            parts = [*BaseMonitor.iter_node(node)]
            parts.reverse()
            MAP = self.NODES.setdefault(parts[0], set())
            for part in parts[1:]:
                MAP.add(part)
                MAP = self.NODES.setdefault(part, set())
            return node
        return list(map(self.define, node()))

    def depend(self, node: str, *depends: str):
        if any((path := n) not in self.NODES for n in (node, *depends)):
            raise ValueError(f"Node {path} not defined")
        self.NODE_DEPENDS.setdefault(node, set()).update(depends)

    def traversal(self, base: str):
        if base not in self.NODES:
            raise ValueError(f"Node {base} not defined")
        result = []
        for node in self.NODES[base]:
            result.append(node)
            result.extend(self.traversal(node))
        return result

    def export(self, owner: Owner) -> dict[str, NodeState]:
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
                state = NodeState(Config.DEFAULT_DIR if self.NODES[dep] else Config.DEFAULT_FILE)
            else:
                state = nodes[dep]
            if dep in self.NODE_DEPENDS:
                for dep_state in map(lambda p: _depend_check(p, cache), self.NODE_DEPENDS[dep]):
                    state &= dep_state
            cache[dep] = state
            return state

        _cache = {}

        for path in nodes:
            if path in self.NODE_DEPENDS:
                for dep_state in map(lambda p: _depend_check(p, _cache), self.NODE_DEPENDS[path]):
                    nodes[path] &= dep_state
        return nodes


class SyncMonitor(ABC, BaseMonitor, Generic[Unpack[Ts]]):
    ATTACHES: list[tuple[Callable[[str], bool], Callable[[str, Owner, Unpack[Ts]], bool]]]

    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def save(self):
        pass

    @abstractmethod
    def get_or_new_owner(self, name: str, priority: Optional[int] = None) -> Owner:
        pass

    @abstractmethod
    def inherit(self, target: Owner, source: Owner, *sources: Owner):
        pass

    @abstractmethod
    def cancel_inherit(self, target: Owner, source: Owner):
        pass

    @abstractmethod
    def all_owners(self) -> Iterable[Owner]:
        pass

    @property
    @abstractmethod
    def default_group(self) -> Owner:
        pass

    @overload
    def attach(self, pattern: str) -> Callable[[Callable[[Owner, Unpack[Ts]], bool]], Callable[[Owner, Unpack[Ts]], bool]]:
        ...

    @overload
    def attach(self, pattern: Callable[[str], bool]) -> Callable[[Callable[[str, Owner, Unpack[Ts]], bool]], Callable[[str, Owner, Unpack[Ts]], bool]]:
        ...

    def attach(self, pattern: Union[str, Callable[[str], bool]]):

        if isinstance(pattern, str):
            def decorator(func: Callable[[Owner, Unpack[Ts]], bool], /):
                self.ATTACHES.append((lambda x: x == pattern, lambda _, y, *args: func(y, *args)))
                return func

            return decorator

        def wrapper(func: Callable[[str, Owner, Unpack[Ts]], bool], /):
            self.ATTACHES.append((pattern, func))
            return func

        return wrapper

    def run_attach(self, owner: Owner, state: NodeState, *args: Unpack[Ts]):
        for node in self.NODES:
            results = []
            for pattern, func in self.ATTACHES:
                if pattern(node):
                    results.append(func(node, owner, *args))
            if results and all(results):
                owner.nodes[node] = state


class AsyncMonitor(ABC, BaseMonitor, Generic[Unpack[Ts]]):
    ATTACHES: list[tuple[Callable[[str], bool], Callable[[str, Owner, Unpack[Ts]], Awaitable[bool]]]]

    @abstractmethod
    async def load(self):
        pass

    @abstractmethod
    async def save(self):
        pass

    @abstractmethod
    async def get_or_new_owner(self, name: str, priority: Optional[int] = None) -> Owner:
        pass

    @abstractmethod
    async def inherit(self, target: Owner, source: Owner, *sources: Owner):
        pass

    @abstractmethod
    async def cancel_inherit(self, target: Owner, source: Owner):
        pass

    @abstractmethod
    async def all_owners(self) -> Iterable[Owner]:
        pass

    @property
    @abstractmethod
    def default_group(self) -> Owner:
        pass

    @overload
    def attach(self, pattern: str) -> Callable[
        [Callable[[Owner, Unpack[Ts]], Awaitable[bool]]], Callable[[Owner, Unpack[Ts]], Awaitable[bool]]]:
        ...

    @overload
    def attach(self, pattern: Callable[[str], bool]) -> Callable[
        [Callable[[str, Owner, Unpack[Ts]], Awaitable[bool]]], Callable[[str, Owner, Unpack[Ts]], Awaitable[bool]]]:
        ...

    def attach(self, pattern: Union[str, Callable[[str], bool]]):
        if isinstance(pattern, str):
            def decorator(func: Callable[[Owner, Unpack[Ts]], Awaitable[bool]], /):
                self.ATTACHES.append((lambda x: x == pattern, lambda _, y, *args: func(y, *args)))
                return func

            return decorator

        def wrapper(func: Callable[[str, Owner, Unpack[Ts]], Awaitable[bool]], /):
            self.ATTACHES.append((pattern, func))
            return func

        return wrapper

    async def run_attach(self, owner: Owner, state: NodeState, *args: Unpack[Ts]):
        for node in self.NODES:
            tasks = []
            for pattern, func in self.ATTACHES:
                if pattern(node):
                    tasks.append(func(node, owner, *args))
            if tasks and all(await asyncio.gather(*tasks)):
                owner.nodes[node] = state
