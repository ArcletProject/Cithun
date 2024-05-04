from pathlib import Path

from arclet.cithun import Node, NodeState, PE, context
from arclet.cithun.builtins.monitor import DefaultMonitor
from arclet.cithun.node import CHILD_MAP

monitor = DefaultMonitor(Path("monitor.json"))

baz = Node("/foo/bar/baz").mkdir(parents=True)
qux = (baz / "qux").touch()
cmd = Node("/command").mkdir()
test = (cmd / "test").mkdir()
sub = (test / "sub").touch()
test1 = (cmd / "test1").mkdir()
sub1 = (test1 / "sub1").touch()

with context(scope="main"), monitor.transaction():
    admin = monitor.new_group("admin", 100)
    PE.root.set(admin, baz, NodeState("vma"))

    user = monitor.new_user("cithun")
    monitor.user_inherit(user, admin)

    assert PE(user).get(user, baz).most == NodeState("vma")
    assert not PE.root.get(user, qux).most.available

    PE.root.set(user, qux, NodeState(7))
    assert PE.root.get(user, qux).most.available

    PE.root.set(admin, baz, NodeState("v-a"))
    try:
        PE(user).set(user, qux, NodeState("vm-"))
    except PermissionError as e:
        print(e)  # Permission denied as /baz/ is not modifiable

    PE.root.set(user, Node("/command/*"), NodeState("vma"))
    assert PE(user).get(user, sub).most == NodeState("vma")
