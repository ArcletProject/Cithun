import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable
from weakref import WeakValueDictionary

from arclet.cithun import Group, User
from arclet.cithun.monitor import SyncMonitor

from .owner import DefaultGroup, DefaultUser


class DefaultMonitor(SyncMonitor):
    def __init__(self, file: Path):
        if not file.suffix.startswith(".json"):
            raise ValueError(file)
        self.file = file
        self.USER_TABLE = WeakValueDictionary()
        self.GROUP_TABLE = WeakValueDictionary()

    def new_group(self, name: str, priority: int):
        if name in self.GROUP_TABLE:
            raise ValueError(f"Group {name} already exists")
        group = DefaultGroup(name, priority)
        self.GROUP_TABLE[name] = group
        return group

    def new_user(self, name: str):
        if name in self.USER_TABLE:
            raise ValueError(f"User {name} already exists")
        user = DefaultUser(name)
        self.USER_TABLE[name] = user
        return user

    def load(self):
        if self.file.exists():
            with self.file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            users = {name: DefaultUser.parse(raw) for name, raw in data["users"].items()}
            groups = {name: DefaultGroup.parse(raw) for name, raw in data["groups"].items()}
            self.USER_TABLE.update(users)
            self.GROUP_TABLE.update(groups)
            for group in groups.values():
                group.inherits = [self.GROUP_TABLE[gp.name] for gp in group.inherits]
            for user in users.values():
                user.inherits = [self.GROUP_TABLE[gp.name] for gp in user.inherits]
            del users, groups
        else:
            with self.file.open("w+", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False)

    def save(self):
        data = {
            "users": {user.name: user.dump() for user in self.USER_TABLE.values()},
            "groups": {group.name: group.dump() for group in self.GROUP_TABLE.values()},
        }
        with self.file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def group_inherit(self, target: Group, *groups: Group):
        for group in groups:
            if group not in target.inherits:
                target.inherits.append(group)

    def user_inherit(self, target: User, *groups: Group):
        for group in groups:
            if group not in target.inherits:
                target.inherits.append(group)

    def user_leave(self, target: User, group: Group):
        if group in target.inherits:
            target.inherits.remove(group)

    @contextmanager
    def transaction(self):
        yield
        self.save()

    def all_users(self) -> Iterable[User]:
        return self.USER_TABLE.values()

    def all_groups(self) -> Iterable[Group]:
        return self.GROUP_TABLE.values()
