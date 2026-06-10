from __future__ import annotations

import json
from dataclasses import asdict

from arclet.cithun.store import BaseStore


class JsonStore(BaseStore):
    # def load(self):
    #     if self.file.exists():
    #         with self.file.open("r", encoding="utf-8") as f:
    #             data = json.load(f)
    #         user_rows = data.get("users", [])
    #         for row in user_rows:
    #             user = User(**row)
    #             self.users[user.id] = user
    #         role_rows = data.get("roles", [])
    #         for row in role_rows:
    #             role = Role(**row)
    #             self.roles[role.id] = role
    #
    #         acl_rows = data.get("acls", [])
    #         for row in acl_rows:
    #             acl = AclEntry(**row)
    #             self.acls[acl.identity] = acl
    #         track_rows = data.get("tracks", [])
    #         for row in track_rows:
    #             levels = row.pop("levels", [])
    #             track = Track(**row)
    #             for level_row in levels:
    #                 level = TrackLevel(**level_row)
    #                 track.levels.append(level)
    #             self.tracks[track.id] = track
    #     else:
    #         with self.file.open("w+", encoding="utf-8") as f:
    #             json.dump({}, f, ensure_ascii=False)

    def save(self, scope: str):
        data = {
            "users": [asdict(user) for user in self.users.values()],
            "roles": [asdict(role) for role in self.roles.values()],
            "acls": [asdict(acl) for acl in self.acls.values()],
            "tracks": [asdict(track) for track in self.tracks.values()],
        }

        with open(f"{scope}.json", "w+", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
