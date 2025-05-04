from abc import ABC, abstractmethod
from collections.abc import Awaitable
from typing import Callable, Iterable, Optional, TypeVar

from .ctx import Context
from .node import NodeState
from .owner import Owner

Provider = Callable[[Owner, Context], bool]
AProvider = Callable[[Owner, Context], Awaitable[bool]]
TProvider = TypeVar("TProvider", bound=Provider)
TAProvider = TypeVar("TAProvider", bound=AProvider)


class SyncMonitor(ABC):
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

    @abstractmethod
    def provide(self, node: str, state: NodeState) -> Callable[[TProvider], TProvider]:
        pass

    @abstractmethod
    def apply(self, owner: Owner, name: str, ctx: Optional[Context] = None):
        pass


class AsyncMonitor(ABC):
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

    @abstractmethod
    async def provide(self, node: str, state: NodeState) -> Callable[[TAProvider], TAProvider]:
        pass

    @abstractmethod
    async def apply(self, owner: Owner, name: str, ctx: Optional[Context] = None):
        pass
