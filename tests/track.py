from arclet.cithun import Permission
from arclet.cithun.builtins import DBSystem

system = DBSystem("data.db")

with system.transaction():
    AUTH_1 = system.create_role("ROLE_AUTH_1", "AUTH_1")
    AUTH_2 = system.create_role("ROLE_AUTH_2", "AUTH_2")
    AUTH_3 = system.create_role("ROLE_AUTH_3", "AUTH_3")
    system.inherit(AUTH_2, AUTH_1)
    system.inherit(AUTH_3, AUTH_2)

    alice = system.create_user("alice", "Alice")
    auths = system.create_track("Authority")
    system.extend_track(auths, [AUTH_1, AUTH_2, AUTH_3], ["member", "admin", "owner"])

    system.assign(AUTH_1, "app.data", Permission.AVAILABLE)
    system.assign(AUTH_2, "app.data", Permission.VISIT)
    system.assign(AUTH_3, "app.data", Permission.MODIFY)

    system.set_user_track_level(alice, auths, -1)

    system.promote_track(alice, auths)
    assert system.get_user_track_level(alice, auths).level_name == "member"  # type: ignore
    assert system.test(alice, "app.data", Permission.AVAILABLE)
    assert not system.test(alice, "app.data", Permission.VISIT)
    system.promote_track(alice, auths)
    assert system.get_user_track_level(alice, auths).level_name == "admin"  # type: ignore
    assert system.test(alice, "app.data", Permission.VISIT)
    assert not system.test(alice, "app.data", Permission.MODIFY)
    system.promote_track(alice, auths)
    assert system.get_user_track_level(alice, auths).level_name == "owner"  # type: ignore
    assert system.test(alice, "app.data", Permission.MODIFY)
    #
    # system.assign(AUTH_4, "app.secret", Permission.AVAILABLE | Permission.VISIT)
    # system.assign(alice, "app.data", Permission.MODIFY)
    # system.assign(bob, "app.config", Permission.MODIFY)
    #
    # system.depend(alice, "app.data", AUTH_4, "app.secret", Permission.VISIT)
    # system.depend(bob, "app.config", alice, "app.data", Permission.VISIT)
    #
    #
    system.assign(AUTH_2, "command.foo", Permission.AVAILABLE)
    assert system.test(alice, "command.foo", Permission.AVAILABLE)
