from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from arclet.cithun.model import AclEntry, Permission, ResourceNode, Role, Track, TrackLevel, User
from arclet.cithun.store import BaseStore


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

        CREATE TABLE IF NOT EXISTS acls (
            subject_type TEXT NOT NULL,  -- 'USER' or 'ROLE'
            subject_id TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            allow_mask INTEGER NOT NULL,
            deny_mask INTEGER DEFAULT 0,
            PRIMARY KEY (subject_type, subject_id, resource_id)
        );

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
        if acl.identity in self.acls:
            return self.acls[acl.identity]
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO acls (subject_type, subject_id, resource_id, allow_mask, deny_mask) VALUES (?, ?, ?, ?, ?);",
            (acl.subject_type.value, acl.subject_id, acl.resource_id, acl.allow_mask, acl.deny_mask),
        )
        self.conn.commit()
        self.acls[acl.identity] = acl

    def _add_resource(self, res: ResourceNode):
        if res.id in self.resources:
            return self.resources[res.id]
        self.resources[res.id] = res
        return res

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

    def update_acl(self, acl: AclEntry, allow_mask: Permission, deny_mask: Permission | None = None) -> None:
        acl.allow_mask = allow_mask
        if deny_mask is not None:
            acl.deny_mask = deny_mask
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE acls SET allow_mask = ?, deny_mask = ? "
            "WHERE subject_type = ? AND subject_id = ? AND resource_id = ?;",
            (acl.allow_mask, acl.deny_mask, acl.subject_type.value, acl.subject_id, acl.resource_id),
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
        cursor.execute("SELECT subject_type, subject_id, resource_id, allow_mask, deny_mask FROM acls;")
        for row in cursor.fetchall():
            acl = AclEntry(*row)
            self.acls[acl.identity] = acl
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
