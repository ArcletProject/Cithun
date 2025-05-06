from pathlib import Path

from arclet.cithun import PE, NodeState, define
from arclet.cithun.builtins.monitor import DefaultMonitor

monitor = DefaultMonitor(Path("function_monitor.json"))

define("foo.bar.baz.qux")
define("command.test.sub")
define("command.test1.sub1")

with monitor.transaction():
    admin = monitor.get_or_new_owner("admin", 100)
    PE.root.set(admin, "foo.bar.baz", NodeState("vma"))

    user = monitor.get_or_new_owner("cithun")
    monitor.inherit(user, admin)

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
