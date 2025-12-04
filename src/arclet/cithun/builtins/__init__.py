from contextlib import contextmanager

from arclet.cithun import PermissionEngine, PermissionExecutor, PermissionService

from .database import SimpleDatabaseStore
from .json import JsonStore


class System(JsonStore, PermissionService[dict], PermissionExecutor[dict]):
    def __init__(self, path):
        JsonStore.__init__(self, path)
        PermissionService.__init__(self, engine=PermissionEngine(), storage=self)
        PermissionExecutor.__init__(self, self, self)

    @contextmanager
    def transaction(self):
        yield
        self.save()


class DBSystem(SimpleDatabaseStore, PermissionService[dict], PermissionExecutor[dict]):
    def __init__(self, path):
        SimpleDatabaseStore.__init__(self, path)
        PermissionService.__init__(self, engine=PermissionEngine(), storage=self)
        PermissionExecutor.__init__(self, self, self)

    @contextmanager
    def transaction(self):
        self.load()
        yield
        self.save()
