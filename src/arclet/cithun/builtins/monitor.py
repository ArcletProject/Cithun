import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Optional

from arclet.cithun.monitor import SyncMonitor
from arclet.cithun.model import Owner
from arclet.cithun.store import STORE

from .owner import DefaultOwner


class DefaultMonitor(SyncMonitor[dict]):
    def load(self):
        if self.file.exists():
            with self.file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            for part, subs in data["nodes"].items():
                STORE.NODES.setdefault(part, set()).update(subs)
            for part, subs in data["depends"].items():
                STORE.NODE_DEPENDS.setdefault(part, set()).update(subs)
            owners = {name: DefaultOwner.parse(raw) for name, raw in data["owners"].items()}
            _default_group = owners.pop("group:default", None)
            self.OWNER_TABLE.update(owners)
            for owner in owners.values():
                owner.inherits = [self.OWNER_TABLE[gp.name] for gp in owner.inherits]
            if _default_group is not None:
                source = self.default_group
                source.nodes.update(_default_group.nodes)
            del owners
        else:
            with self.file.open("w+", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False)

    def save(self):
        data = {
            "owners": {owner.name: owner.dump() for owner in self.OWNER_TABLE.values()},
            "nodes": {part: list(subs) for part, subs in STORE.NODES.items()},
            "depends": {part: list(subs) for part, subs in STORE.NODE_DEPENDS.items()},
        }
        with self.file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_or_new_owner(self, name: str, priority: Optional[int] = None):
        if name in self.OWNER_TABLE:
            return self.OWNER_TABLE[name]
        owner = DefaultOwner(name, priority)
        owner.inherits.append(self.default_group)
        self.OWNER_TABLE[name] = owner
        return owner

    def inherit(self, target: Owner, source: Owner, *sources: Owner):
        for src in [source, *sources]:
            if src not in target.inherits:
                target.inherits.append(src)

    def cancel_inherit(self, target: Owner, source: Owner):
        if source in target.inherits:
            target.inherits.remove(source)

    def all_owners(self) -> Iterable[Owner]:
        return self.OWNER_TABLE.values()

    def __init__(self, file: Path):
        if not file.suffix.startswith(".json"):
            raise ValueError(file)
        self.file = file
        self.OWNER_TABLE = {"group:default": DefaultOwner("group:default", 100)}
        self.ATTACHES = []

    @contextmanager
    def transaction(self):
        yield
        self.save()

    @property
    def default_group(self) -> Owner:
        return self.OWNER_TABLE["group:default"]
