from contextlib import contextmanager
from arclet.cithun import PermissionEngine, PermissionExecutor

from .service import DefaultPermissionService
from .store import JsonStore


class System(PermissionExecutor):
    def __init__(self, path):
        self.store = JsonStore(path)
        self.service = DefaultPermissionService(engine=PermissionEngine(), storage=self.store)
        super().__init__(storage=self.store, perm_service=self.service)

    def load(self):
        self.store.load()

    def save(self):
        self.store.save()

    @contextmanager
    def transaction(self):
        yield
        self.save()
