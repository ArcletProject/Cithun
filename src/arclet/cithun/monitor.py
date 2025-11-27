import asyncio
from abc import ABC, abstractmethod
from collections.abc import Awaitable
from typing import Iterable, Optional, Generic, Callable, overload, Union
from typing_extensions import TypeVarTuple, Unpack

from .model import Owner, NodeState
from .store import STORE

Ts = TypeVarTuple("Ts")


class SyncMonitor(ABC, Generic[Unpack[Ts]]):
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
        for node in STORE.NODES:
            results = []
            for pattern, func in self.ATTACHES:
                if pattern(node):
                    results.append(func(node, owner, *args))
            if results and all(results):
                owner.nodes[node] = state


class AsyncMonitor(ABC, Generic[Unpack[Ts]]):
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

    @overload
    def attach(self, pattern: str) -> Callable[[Callable[[Owner, Unpack[Ts]], Awaitable[bool]]], Callable[[Owner, Unpack[Ts]], Awaitable[bool]]]:
        ...

    @overload
    def attach(self, pattern: Callable[[str], bool]) -> Callable[[Callable[[str, Owner, Unpack[Ts]], Awaitable[bool]]], Callable[[str, Owner, Unpack[Ts]], Awaitable[bool]]]:
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
        for node in STORE.NODES:
            tasks = []
            for pattern, func in self.ATTACHES:
                if pattern(node):
                    tasks.append(func(node, owner, *args))
            if tasks and all(await asyncio.gather(*tasks)):
                owner.nodes[node] = state
