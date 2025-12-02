from contextlib import contextmanager
from arclet.cithun import PermissionEngine, PermissionExecutor

from .service import DefaultPermissionService
from .store import JsonStore, SimpleDatabaseStore


class System(JsonStore, DefaultPermissionService, PermissionExecutor):
    def __init__(self, path):
        JsonStore.__init__(self, path)
        DefaultPermissionService.__init__(self, engine=PermissionEngine(), storage=self)
        PermissionExecutor.__init__(self, self, self)

    @contextmanager
    def transaction(self):
        yield
        self.save()


class DBSystem(SimpleDatabaseStore, DefaultPermissionService, PermissionExecutor):
    def __init__(self, path):
        SimpleDatabaseStore.__init__(self, path)
        DefaultPermissionService.__init__(self, engine=PermissionEngine(), storage=self)
        PermissionExecutor.__init__(self, self, self)

    @contextmanager
    def transaction(self):
        yield
        self.save()
