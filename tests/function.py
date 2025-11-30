from pathlib import Path

from arclet.cithun import Permission, User, Role, ResourceNode
from arclet.cithun.builtins import System

monitor = System(Path("function_monitor.json"))

monitor.store.define("foo.bar.baz.qux")
monitor.store.define("command.test.sub")
monitor.store.define("command.test1.sub1")

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
    monitor.storage.define("foo.bar.baz")
    monitor.storage.define("foo.bar.baz.qux")
    admin = monitor.store.add_role(Role("role:admin", "Administrator"))
    admin_baz = monitor.suset(admin, "foo.bar.baz", Permission.VISIT | Permission.AVAILABLE | Permission.MODIFY)

    user = monitor.store.add_user(User("user:cithun", "cithun"))
    monitor.store.inherit(user, admin)

    # monitor.run_attach(user, NodeState("vma"), {})

    assert monitor.test(user, "foo.bar.baz", Permission.VISIT)
    assert not monitor.test(user, "foo.bar.baz.qux", Permission.AVAILABLE)

    assert monitor.suset(user, "foo.bar.baz.qux", Permission(7))
    assert monitor.get(user, "foo.bar.baz.qux") == Permission.VISIT | Permission.AVAILABLE | Permission.MODIFY

    monitor.suset(admin, "foo.bar.baz", Permission.VISIT | Permission.AVAILABLE)
    try:
        monitor.set(user, user, "foo.bar.baz.qux", Permission.VISIT | Permission.MODIFY)
    except PermissionError as e:
        print(e)  # Permission denied as "foo.bar.baz" is not modifiable

    # PE.root.set(user, "command.*", NodeState("vma"))
    # assert PE(user).get(user, "command.test.sub") == NodeState("vma")
