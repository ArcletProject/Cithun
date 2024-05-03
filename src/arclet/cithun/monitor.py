from abc import ABC, abstractmethod

from .owner import Group, User


class SyncMonitor(ABC):
    @abstractmethod
    def new_group(self, name: str, priority: int) -> Group:
        pass

    @abstractmethod
    def new_user(self, name: str) -> User:
        pass

    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def save(self):
        pass

    @abstractmethod
    def group_inherit(self, target: Group, *groups: Group):
        pass

    @abstractmethod
    def user_inherit(self, target: User, *groups: Group):
        pass

    @abstractmethod
    def user_leave(self, target: User, group: Group):
        pass


class AsyncMonitor(ABC):
    @abstractmethod
    async def new_group(self, name: str, priority: int) -> Group:
        pass

    @abstractmethod
    async def new_user(self, name: str) -> User:
        pass

    @abstractmethod
    async def load(self):
        pass

    @abstractmethod
    async def save(self):
        pass

    @abstractmethod
    async def group_inherit(self, target: Group, *groups: Group):
        pass

    @abstractmethod
    async def user_inherit(self, target: User, *groups: Group):
        pass

    @abstractmethod
    async def user_leave(self, target: User, group: Group):
        pass
