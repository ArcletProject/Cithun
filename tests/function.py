from pathlib import Path

from arclet.cithun import Node, NodeState, context, PermissionExecutor
from arclet.cithun.builtins.monitor import DefaultMonitor

monitor = DefaultMonitor(Path("monitor.json"))

baz = Node("/foo/bar/baz").mkdir(parents=True)
qux = (baz / "qux").touch()

with context(scope="main"):
    admin = monitor.new_group('admin', 100)
    PermissionExecutor.root.set(admin, baz, NodeState("vma"))

    user = monitor.new_user('cithun')
    monitor.user_inherit(user, admin)

    assert PermissionExecutor.root.get(user, baz).most == NodeState("vma")
    assert not PermissionExecutor.root.get(user, qux).most.available

    PermissionExecutor.root.set(user, qux, NodeState(7))
    assert PermissionExecutor.root.get(user, qux).most.available

    PermissionExecutor.root.set(admin, baz, NodeState("v-a"))
    try:
        PermissionExecutor(user).set(user, qux, NodeState("vm-"))
    except PermissionError as e:
        print(e)  # Permission denied as /baz/ is not modifiable
