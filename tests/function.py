from pathlib import Path

from arclet.cithun import Permission
from arclet.cithun.builtins import System

monitor = System("./function_monitor.json")
monitor.define("foo.bar.baz")
monitor.define("foo.bar.baz.qux")
monitor.define("command.test.sub")
monitor.define("command.test1.sub1")

# @monitor.service.engine.register_strategy
# def auth_handler(
#     user: User,
#     resource: ResourceNode,
#     context: tuple[dict],
#     current_mask: int,
#     permission_lookup
# ):

# @monitor.attach(lambda pat: pat.startswith("auth."))
# def auth_handler(node: str, owner, state) -> bool:
#     level = int(node.split(".")[-1])
#     if level == 4:
#         return any(ow.name == "owner" for ow in owner.inherits)
#     if level == 3:
#         return any(ow.name == "admin" for ow in owner.inherits)
#     return True


with monitor.transaction():
    admin = monitor.create_role("role:admin", "Administrator")
    monitor.suset(admin, "foo.bar.baz", Permission.VISIT | Permission.AVAILABLE | Permission.MODIFY)

    user = monitor.create_user("user:cithun", "cithun")
    monitor.inherit(user, admin)

    # monitor.run_attach(user, NodeState("vma"), {})

    assert monitor.test(user, "foo.bar.baz", Permission.VISIT)
    assert not monitor.test(user, "foo.bar.baz.qux", Permission.AVAILABLE)

    monitor.suset(user, "foo.bar.baz.qux", Permission(7))
    assert monitor.get(user, "foo.bar.baz.qux") == Permission.VISIT | Permission.AVAILABLE | Permission.MODIFY

    monitor.suset(admin, "foo.bar.baz", Permission.VISIT | Permission.AVAILABLE)
    try:
        monitor.set(user, user, "foo.bar.baz.qux", Permission.VISIT | Permission.MODIFY)
    except PermissionError as e:
        print(e)  # Permission denied as "foo.bar.baz" is not modifiable

    monitor.suset(user, "command.test", Permission(5))
    monitor.suset(user, "command.test.*", Permission(5))
    assert monitor.get(user, "command.test.sub") == Permission(5)


print(monitor.resource_tree())
print(monitor.permission_on(user))
