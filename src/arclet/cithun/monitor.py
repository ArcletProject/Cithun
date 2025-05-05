from abc import ABC, abstractmethod
from typing import Iterable, Optional

from .owner import Owner


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

    @property
    @abstractmethod
    def default_group(self) -> Owner:
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

    @property
    @abstractmethod
    def default_group(self) -> Owner:
        pass
