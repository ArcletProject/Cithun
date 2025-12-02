import os
import json
import sqlite3
from dataclasses import astuple
from pathlib import Path

from arclet.cithun.store import BaseStore
from arclet.cithun.model import User, Role, AclEntry, AclDependency, ResourceNode, Track, TrackLevel


class JsonStore(BaseStore):
    def load(self):
        if self.file.exists():
            with self.file.open("r", encoding="utf-8") as f:
                data = json.load(f)
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
                dep_rows = alc_dependency_rows.get(f"{acl.subject_type}_{acl.subject_id}_{acl.resource_id}", [])
                for dep_row in dep_rows:
                    dep = AclDependency(*dep_row)
                    acl.dependencies.append(dep)
                self.acls.append(acl)
            track_rows = data.get("tracks", [])
            track_level_rows = data.get("track_levels", {})
            for row in track_rows:
                track = Track(*row)
                level_rows = track_level_rows.get(track.id, [])
                for level_row in level_rows:
                    level = TrackLevel(*level_row)
                    track.levels.append(level)
                self.tracks[track.id] = track
        else:
            with self.file.open("w+", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False)

    def save(self):
        data = {
            "$user_metadata": "id, name, role_ids",
            "users": [astuple(user) for user in self.users.values()],
            "$role_metadata": "id, name, parent_role_ids",
            "roles": [astuple(role) for role in self.roles.values()],
            "$resource_metadata": "id, name, parent_id, inherit_mode, type",
            "resources": [astuple(res) for res in self.resources.values()],
            "$acl_metadata": "subject_type, subject_id, resource_id, allow_mask, deny_mask",
            "acls": [],
            "$acl_dependency_metadata": "subject_type, subject_id, resource_id, required_mask",
            "acl_dependencies": {},
            "$track_metadata": "id, name",
            "tracks": [],
            "$track_level_metadata": "role_id, level_name, level_index",
            "track_levels": {},
        }
        for acl in self.acls:
            acl_row = astuple(acl)
            data["acls"].append(acl_row[:4])  # 不保存 dependencies 字段
            dep_rows = [astuple(dep) for dep in acl.dependencies]
            if dep_rows:
                data["acl_dependencies"][f"{acl.subject_type}_{acl.subject_id}_{acl.resource_id}"] = dep_rows
        for track in self.tracks.values():
            track_row = astuple(track)
            data["tracks"].append(track_row[:2])  # 不保存 levels 字段
            level_rows = [astuple(level) for level in track.levels]
            if level_rows:
                data["track_levels"][track.id] = level_rows
        with self.file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def __init__(self, file: os.PathLike[str]):
        file = Path(file)
        if not file.suffix.startswith(".json"):
            raise ValueError(file)
        self.file = file
        super().__init__()


class SimpleDatabaseStore(BaseStore):
    def __init__(self, file: os.PathLike[str]):
        file = Path(file)
        self.file = file
        self.conn = sqlite3.connect(self.file)
        super().__init__()
        self.ensure_table()

    def ensure_table(self):
        sql = """\
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS roles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_roles (
            user_id TEXT,
            role_id TEXT,
            PRIMARY KEY (user_id, role_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
        );
            
        CREATE TABLE IF NOT EXISTS role_inherits (
            role_id TEXT,
            parent_role_id TEXT,
            PRIMARY KEY (role_id, parent_role_id),
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_role_id) REFERENCES roles(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS resources (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            parent_id TEXT NULL,
            inherit_mode INTEGER DEFAULT 0,  -- 0: INHERIT, 1: MERGE, 2: OVERRIDE
            type TEXT NOT NULL DEFAULT 'GENERIC',  -- FILE / DIR / PROJECT / etc.
            FOREIGN KEY (parent_id) REFERENCES resources(id) ON DELETE CASCADE
        );
        CREATE INDEX idx_resources_parent_id ON resources(parent_id);
            
        CREATE TABLE IF NOT EXISTS acls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_type TEXT NOT NULL,  -- 'USER' or 'ROLE'
            subject_id TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            allow_mask INTEGER NOT NULL,
            deny_mask INTEGER DEFAULT 0,
            FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
        );
            
        CREATE INDEX idx_acls_resource_id ON acls(resource_id);
        CREATE INDEX idx_acls_subject ON acls(subject_type, subject_id);
        
        CREATE TABLE IF NOT EXISTS acl_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            acl_id INTEGER NOT NULL,
            dep_subject_type TEXT NOT NULL,
            dep_subject_id TEXT NOT NULL,
            dep_resource_id TEXT NOT NULL,
            required_mask INTEGER NOT NULL,
            FOREIGN KEY (acl_id) REFERENCES acls(id) ON DELETE CASCADE,
            FOREIGN KEY (dep_resource_id) REFERENCES resources(id) ON DELETE CASCADE
        );
        
        CREATE INDEX idx_acl_deps_acl_id  ON acl_dependencies(acl_id);
        CREATE INDEX idx_acl_deps_dep_subject ON acl_dependencies(dep_subject_type, dep_subject_id);
        CREATE INDEX idx_acl_deps_dep_resource ON acl_dependencies(dep_resource_id);
        
        CREATE TABLE IF NOT EXISTS tracks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS track_levels (
            track_id TEXT,
            role_id TEXT,
            level_name TEXT NOT NULL,
            level_index INTEGER NOT NULL,
            PRIMARY KEY (track_id, role_id),
            FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
        );
        CREATE INDEX idx_track_levels_track_id ON track_levels(track_id);
        CREATE INDEX idx_track_levels_role_id ON track_levels(role_id);
        """
        self.conn.executescript(sql)
        self.conn.commit()

    def load(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name FROM users;")
        for row in cursor.fetchall():
            user = User(*row, role_ids=[])
            self.users[user.id] = user
        cursor.execute("SELECT id, name FROM roles;")
        for row in cursor.fetchall():
            role = Role(*row, parent_role_ids=[])
            self.roles[role.id] = role
        for user in self.users.values():
            cursor.execute(
                "SELECT role_id FROM user_roles WHERE user_id = ?;",
                (user.id,)
            )
            role_ids = [r[0] for r in cursor.fetchall()]
            user.role_ids.extend(role_ids)
        for role in self.roles.values():
            cursor.execute(
                "SELECT parent_role_id FROM role_inherits WHERE role_id = ?;",
                (role.id,)
            )
            parent_role_ids = [r[0] for r in cursor.fetchall()]
            role.parent_role_ids.extend(parent_role_ids)
        cursor.execute("SELECT id, name, parent_id, inherit_mode, type FROM resources;")
        for row in cursor.fetchall():
            resource = ResourceNode(*row)
            self.resources[resource.id] = resource
        cursor.execute(
            "SELECT id, subject_type, subject_id, resource_id, allow_mask, deny_mask FROM acls;"
        )
        acl_ids = []
        for row in cursor.fetchall():
            acl = AclEntry(*row[1:], dependencies=[])
            self.acls.append(acl)
            acl_ids.append(row[0])
        for acl, acl_id in zip(self.acls, acl_ids):
            cursor.execute(
                "SELECT dep_subject_type, dep_subject_id, dep_resource_id, required_mask "
                "FROM acl_dependencies WHERE acl_id = ?;",
                (acl_id,)
            )
            for dep_row in cursor.fetchall():
                dep = AclDependency(*dep_row)
                acl.dependencies.append(dep)
        cursor.execute("SELECT id, name FROM tracks;")
        for row in cursor.fetchall():
            track = Track(*row, levels=[])
            self.tracks[track.id] = track
        for track in self.tracks.values():
            cursor.execute(
                "SELECT role_id, level_name, level_index FROM track_levels WHERE track_id = ?;",
                (track.id,)
            )
            for level_row in cursor.fetchall():
                level = TrackLevel(*level_row)
                track.levels.append(level)

    def save(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM users;")
        for user in self.users.values():
            cursor.execute(
                "INSERT INTO users (id, name) VALUES (?, ?);",
                (user.id, user.name)
            )
            for role_id in user.role_ids:
                cursor.execute(
                    "INSERT INTO user_roles (user_id, role_id) VALUES (?, ?);",
                    (user.id, role_id)
                )
        cursor.execute("DELETE FROM roles;")
        for role in self.roles.values():
            cursor.execute(
                "INSERT INTO roles (id, name) VALUES (?, ?);",
                (role.id, role.name)
            )
            for parent_role_id in role.parent_role_ids:
                cursor.execute(
                    "INSERT INTO role_inherits (role_id, parent_role_id) VALUES (?, ?);",
                    (role.id, parent_role_id)
                )
        cursor.execute("DELETE FROM resources;")
        for resource in self.resources.values():
            cursor.execute(
                "INSERT INTO resources (id, name, parent_id, inherit_mode, type) "
                "VALUES (?, ?, ?, ?, ?);",
                (resource.id, resource.name, resource.parent_id,
                 resource.inherit_mode.value, resource.type)
            )
        cursor.execute("DELETE FROM acls;")
        for acl in self.acls:
            cursor.execute(
                "INSERT INTO acls (id, subject_type, subject_id, resource_id, allow_mask, deny_mask) "
                "VALUES (?, ?, ?, ?, ?, ?);",
                (None, acl.subject_type.value, acl.subject_id,
                 acl.resource_id, acl.allow_mask, acl.deny_mask)
            )
            acl_id = cursor.lastrowid
            for dep in acl.dependencies:
                cursor.execute(
                    "INSERT INTO acl_dependencies (acl_id, dep_subject_type, dep_subject_id, "
                    "dep_resource_id, required_mask) VALUES (?, ?, ?, ?, ?);",
                    (acl_id, dep.subject_type.value, dep.subject_id,
                     dep.resource_id, dep.required_mask)
                )
        cursor.execute("DELETE FROM tracks;")
        for track in self.tracks.values():
            cursor.execute(
                "INSERT INTO tracks (id, name) VALUES (?, ?);",
                (track.id, track.name)
            )
            for level in track.levels:
                cursor.execute(
                    "INSERT INTO track_levels (track_id, role_id, level_name, level_index) "
                    "VALUES (?, ?, ?, ?);",
                    (track.id, level.role_id, level.level_name, level.level_index)
                )
        self.conn.commit()