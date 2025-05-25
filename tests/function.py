from pathlib import Path

from arclet.cithun import PE, NodeState
from arclet.cithun.builtins.monitor import DefaultMonitor

monitor = DefaultMonitor(Path("function_monitor.json"))

monitor.define("foo.bar.baz.qux")
monitor.define("command.test.sub")
monitor.define("command.test1.sub1")
monitor.define(lambda: (f"auth.{i}" for i in range(1, 5)))


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
    PE.root(monitor).set(admin, "foo.bar.baz", NodeState("vma"))

    user = monitor.get_or_new_owner("cithun")
    monitor.inherit(user, admin)

    monitor.run_attach(user, NodeState("vma"), {})

    assert PE(user, monitor).get(user, "foo.bar.baz") == NodeState("vma")
    assert not PE.root(monitor).get(user, "foo.bar.baz.qux").available

    PE.root(monitor).set(user, "foo.bar.baz.qux", NodeState(7))
    assert PE.root(monitor).get(user, "foo.bar.baz.qux").available

    PE.root(monitor).set(admin, "foo.bar.baz", NodeState("v-a"))
    try:
        PE(user, monitor).set(user, "foo.bar.baz.qux", NodeState("vm-"))
    except PermissionError as e:
        print(e)  # Permission denied as "foo.bar.baz" is not modifiable

    PE.root(monitor).set(user, "command.*", NodeState("vma"))
    assert PE(user, monitor).get(user, "command.test.sub") == NodeState("vma")
