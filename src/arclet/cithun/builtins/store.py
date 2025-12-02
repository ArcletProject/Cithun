import json
from dataclasses import astuple
from pathlib import Path

from arclet.cithun.store import BaseStore
from arclet.cithun.model import User, Role, AclEntry, AclDependency, ResourceNode


class JsonStore(BaseStore):
    def load(self):
        if self.file.exists():
            with self.file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._acl_counter = data.get("acl_counter", 0)
            user_rows = data.get("users", [])
            for row in user_rows:
                user = User(*row)
                self.users[user.id] = user
            role_rows = data.get("roles", [])
            for row in role_rows:
                role = Role(*row)
                self.roles[role.id] = role
            resource_rows = data.get("resources", [])
            for row in resource_rows:
                resource = ResourceNode(*row)
                self.resources[resource.id] = resource
            acl_rows = data.get("acls", [])
            alc_dependency_rows = data.get("acl_dependencies", {})
            for row in acl_rows:
                acl = AclEntry(*row)
                dep_rows = alc_dependency_rows.get(acl.id, [])
                for dep_row in dep_rows:
                    dep = AclDependency(*dep_row)
                    acl.dependencies.append(dep)
                self.acls.append(acl)
        else:
            with self.file.open("w+", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False)

    def save(self):
        data = {
            "acl_counter": self._acl_counter,
            "users": [astuple(user) for user in self.users.values()],
            "roles": [astuple(role) for role in self.roles.values()],
            "resources": [astuple(res) for res in self.resources.values()],
            "acls": [],
            "acl_dependencies": {},
        }
        for acl in self.acls:
            acl_row = astuple(acl)
            data["acls"].append(acl_row[:5])  # 不保存 dependencies 字段
            dep_rows = [astuple(dep) for dep in acl.dependencies]
            if dep_rows:
                data["acl_dependencies"][acl.id] = dep_rows
        with self.file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def __init__(self, file: Path):
        if not file.suffix.startswith(".json"):
            raise ValueError(file)
        self.file = file
        super().__init__()
