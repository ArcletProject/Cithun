from pathlib import Path

from arclet.cithun import PE, NodeState
from arclet.cithun.builtins.monitor import DefaultMonitor

monitor = DefaultMonitor(Path("function_monitor.json"))

monitor.define("foo.bar.baz.qux")
monitor.define("command.test.sub")
monitor.define("command.test1.sub1")

with monitor.transaction():
    admin = monitor.get_or_new_owner("admin", 100)
    PE.root(monitor).set(admin, "foo.bar.baz", NodeState("vma"))

    user = monitor.get_or_new_owner("cithun")
    monitor.inherit(user, admin)

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
