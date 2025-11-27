from pathlib import Path

from arclet.cithun import PE, NodeState, store
from arclet.cithun.builtins.monitor import DefaultMonitor

monitor = DefaultMonitor(Path("function_monitor.json"))

store.define("foo.bar.baz.qux")
store.define("command.test.sub")
store.define("command.test1.sub1")
store.define(lambda: (f"auth.{i}" for i in range(1, 5)))


@monitor.attach(lambda pat: pat.startswith("auth."))
def auth_handler(node: str, owner, state) -> bool:
    level = int(node.split(".")[-1])
    if level == 4:
        return any(ow.name == "owner" for ow in owner.inherits)
    if level == 3:
        return any(ow.name == "admin" for ow in owner.inherits)
    return True


with monitor.transaction():
    admin = monitor.get_or_new_owner("admin", 100)
    PE.root.set(admin, "foo.bar.baz", NodeState("vma"))

    user = monitor.get_or_new_owner("cithun")
    monitor.inherit(user, admin)

    monitor.run_attach(user, NodeState("vma"), {})

    assert PE(user).get(user, "foo.bar.baz") == NodeState("vma")
    assert not PE.root.get(user, "foo.bar.baz.qux").available

    PE.root.set(user, "foo.bar.baz.qux", NodeState(7))
    assert PE.root.get(user, "foo.bar.baz.qux").available

    PE.root.set(admin, "foo.bar.baz", NodeState("v-a"))
    try:
        PE(user).set(user, "foo.bar.baz.qux", NodeState("vm-"))
    except PermissionError as e:
        print(e)  # Permission denied as "foo.bar.baz" is not modifiable

    PE.root.set(user, "command.*", NodeState("vma"))
    assert PE(user).get(user, "command.test.sub") == NodeState("vma")
