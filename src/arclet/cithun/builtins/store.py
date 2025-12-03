from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import astuple
from pathlib import Path

from arclet.cithun import InheritMode
from arclet.cithun.model import AclDependency, AclEntry, ResourceNode, Role, Track, TrackLevel, User
from arclet.cithun.store import BaseStore


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
            "$track_level_metadata": "role_id, level_name",
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
        CREATE INDEX IF NOT EXISTS idx_resources_parent_id ON resources(parent_id);

        CREATE TABLE IF NOT EXISTS acls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_type TEXT NOT NULL,  -- 'USER' or 'ROLE'
            subject_id TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            allow_mask INTEGER NOT NULL,
            deny_mask INTEGER DEFAULT 0,
            FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_acls_resource_id ON acls(resource_id);
        CREATE INDEX IF NOT EXISTS idx_acls_subject ON acls(subject_type, subject_id);

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

        CREATE INDEX IF NOT EXISTS idx_acl_deps_acl_id  ON acl_dependencies(acl_id);
        CREATE INDEX IF NOT EXISTS idx_acl_deps_dep_subject ON acl_dependencies(dep_subject_type, dep_subject_id);
        CREATE INDEX IF NOT EXISTS idx_acl_deps_dep_resource ON acl_dependencies(dep_resource_id);

        CREATE TABLE IF NOT EXISTS tracks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS track_levels (
            `index` INTEGER,
            track_id TEXT,
            role_id TEXT,
            level_name TEXT NOT NULL,
            PRIMARY KEY (track_id, role_id),
            FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_track_levels_track_id ON track_levels(track_id);
        CREATE INDEX IF NOT EXISTS idx_track_levels_role_id ON track_levels(role_id);
        """
        self.conn.executescript(sql)
        self.conn.commit()

    def create_user(self, uid: str, name: str) -> User:
        if uid in self.users:
            return self.users[uid]
        user = User(uid, name)
        self.users[uid] = user
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO users (id, name) VALUES (?, ?);", (user.id, user.name))
        self.conn.commit()
        return user

    def create_role(self, rid: str, name: str) -> Role:
        if rid in self.roles:
            return self.roles[rid]
        role = Role(rid, name)
        self.roles[rid] = role
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO roles (id, name) VALUES (?, ?);", (role.id, role.name))
        self.conn.commit()
        return role

    def create_track(self, tid: str, name: str | None = None) -> Track:
        if tid in self.tracks:
            return self.tracks[tid]
        track = Track(tid, name or tid)
        self.tracks[tid] = track
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO tracks (id, name) VALUES (?, ?);", (track.id, track.name))
        self.conn.commit()
        return track

    def _add_acl(self, acl: AclEntry):
        target_acl = next(
            (
                i
                for i in self.acls
                if i.subject_type == acl.subject_type
                and i.subject_id == acl.subject_id
                and i.resource_id == acl.resource_id
            ),
            None,
        )
        if target_acl:
            return target_acl
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO acls (subject_type, subject_id, resource_id, allow_mask, deny_mask) "
            "VALUES (?, ?, ?, ?, ?);",
            (acl.subject_type.value, acl.subject_id, acl.resource_id, acl.allow_mask, acl.deny_mask),
        )
        self.conn.commit()
        self.acls.append(acl)

    def define(
        self,
        path: str,
        inherit_mode: InheritMode | None = None,
        type_: str = "GENERIC",
    ) -> ResourceNode:
        old_keys = set(self.resources.keys())
        resource = super().define(path, inherit_mode, type_)
        additional_keys = set(self.resources.keys()) - old_keys
        cursor = self.conn.cursor()
        for rid in additional_keys:
            res = self.resources[rid]
            cursor.execute(
                "INSERT INTO resources (id, name, parent_id, inherit_mode, type) " "VALUES (?, ?, ?, ?, ?);",
                (res.id, res.name, res.parent_id, res.inherit_mode.value, res.type),
            )
        self.conn.commit()
        return resource

    def depend(
        self,
        target_subject: User | Role,
        target_resource_id: str,
        dep_subject: User | Role,
        dep_resource_path: str,
        required_mask: int,
    ) -> AclEntry:
        target_acl = self.get_primary_acl(target_subject, target_resource_id)
        if not target_acl:
            raise ValueError("Target ACL does not exist.")
        dep_res = self.define(dep_resource_path)
        dep = AclDependency(
            subject_type=dep_subject.type,
            subject_id=dep_subject.id,
            resource_id=dep_res.id,
            required_mask=required_mask,
        )
        if dep in target_acl.dependencies:
            return target_acl
        target_acl.dependencies.append(dep)

        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM acls WHERE subject_type = ? AND subject_id = ? AND resource_id = ?;",
            (target_acl.subject_type.value, target_acl.subject_id, target_acl.resource_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError("ACL entry not found after creation.")
        acl_id = row[0]

        cursor.execute(
            "INSERT INTO acl_dependencies (acl_id, dep_subject_type, dep_subject_id, "
            "dep_resource_id, required_mask) VALUES (?, ?, ?, ?, ?);",
            (acl_id, dep.subject_type.value, dep.subject_id, dep.resource_id, dep.required_mask),
        )
        self.conn.commit()
        return target_acl

    def inherit(self, child: User | Role, parent: Role):
        if isinstance(child, Role):
            child_role = self._ensure_role(child)
            self._ensure_role(parent)
            if parent.id not in child_role.parent_role_ids:
                cursor = self.conn.cursor()
                cursor.execute(
                    "INSERT INTO role_inherits (role_id, parent_role_id) VALUES (?, ?);", (child_role.id, parent.id)
                )
                self.conn.commit()
                child_role.parent_role_ids.append(parent.id)
        else:
            user = self._ensure_user(child)
            self._ensure_role(parent)
            if parent.id not in user.role_ids:
                cursor = self.conn.cursor()
                cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?);", (user.id, parent.id))
                self.conn.commit()
                user.role_ids.append(parent.id)

    def add_track_level(self, track: Track, role: Role, name: str | None = None) -> None:
        level = TrackLevel(role.id, name or role.name)
        if level in track.levels:
            return
        track.levels.append(level)
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO track_levels (`index`, track_id, role_id, level_name) VALUES (?, ?, ?, ?);",
            (len(track.levels) - 1, track.id, role.id, level.level_name),
        )
        self.conn.commit()

    def insert_track_level(self, track: Track, index: int, role: Role, name: str | None = None) -> None:
        level = TrackLevel(role.id, name or role.name)
        if level in track.levels:
            return
        track.levels.insert(index, level)
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM track_levels WHERE track_id = ?;", (track.id,))
        for idx, lvl in enumerate(track.levels):
            cursor.execute(
                "INSERT INTO track_levels (`index`, track_id, role_id, level_name) VALUES (?, ?, ?, ?);",
                (idx, track.id, lvl.role_id, lvl.level_name),
            )
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
            cursor.execute("SELECT role_id FROM user_roles WHERE user_id = ?;", (user.id,))
            role_ids = [r[0] for r in cursor.fetchall()]
            user.role_ids.extend(role_ids)
        for role in self.roles.values():
            cursor.execute("SELECT parent_role_id FROM role_inherits WHERE role_id = ?;", (role.id,))
            parent_role_ids = [r[0] for r in cursor.fetchall()]
            role.parent_role_ids.extend(parent_role_ids)
        cursor.execute("SELECT id, name, parent_id, inherit_mode, type FROM resources;")
        for row in cursor.fetchall():
            resource = ResourceNode(*row)
            self.resources[resource.id] = resource
        cursor.execute("SELECT id, subject_type, subject_id, resource_id, allow_mask, deny_mask FROM acls;")
        acl_ids = []
        for row in cursor.fetchall():
            acl = AclEntry(*row[1:], dependencies=[])
            self.acls.append(acl)
            acl_ids.append(row[0])
        for acl, acl_id in zip(self.acls, acl_ids):
            cursor.execute(
                "SELECT dep_subject_type, dep_subject_id, dep_resource_id, required_mask "
                "FROM acl_dependencies WHERE acl_id = ?;",
                (acl_id,),
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
                "SELECT role_id, level_name FROM track_levels WHERE track_id = ? ORDER BY `index` ASC;", (track.id,)
            )
            for level_row in cursor.fetchall():
                level = TrackLevel(*level_row)
                track.levels.append(level)

    def save(self):
        pass
