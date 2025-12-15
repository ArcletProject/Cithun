from contextlib import contextmanager

from arclet.cithun import PermissionEngine, PermissionExecutor, PermissionService

from .attach import Attacher
from .database import SimpleDatabaseStore
from .json import JsonStore


class System(Attacher, JsonStore, PermissionService[dict], PermissionExecutor[dict]):
    def __init__(self, path):
        JsonStore.__init__(self, path)
        PermissionService.__init__(self, engine=PermissionEngine(), storage=self)
        PermissionExecutor.__init__(self, self, self)
        Attacher.__init__(self, self.engine)

    @contextmanager
    def transaction(self):
        yield
        self.save()


class DBSystem(Attacher, SimpleDatabaseStore, PermissionService[dict], PermissionExecutor[dict]):
    def __init__(self, path):
        SimpleDatabaseStore.__init__(self, path)
        PermissionService.__init__(self, engine=PermissionEngine(), storage=self)
        PermissionExecutor.__init__(self, self, self)
        Attacher.__init__(self, self.engine)

    @contextmanager
    def transaction(self):
        self.load()
        yield
        self.save()
