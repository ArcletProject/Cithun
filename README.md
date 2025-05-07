# Cithun

仿照 Linux 下的文件权限系统实现的权限管理系统。

WIP

## 特性

- 通过类似 Linux 下的文件权限系统的方式管理权限
- 支持用户组
- 支持用户组继承

## Example

```python
from arclet.cithun import SyncMonitor, NodeState, PE, ROOT, define

monitor = SyncMonitor()

baz = define("foo.bar.baz")
qux = define("foo.bar.baz.qux")

admin = monitor.get_or_new_owner('group:admin', 100)
ROOT.set(admin, baz, NodeState("vma"))

user = monitor.get_or_new_owner('user:cithun')
monitor.inherit(user, admin)

assert ROOT.get(user, baz) == NodeState("vma")
assert not ROOT.get(user, qux).available

ROOT.set(user, qux, NodeState(7))
assert ROOT.get(user, qux).available

ROOT.set(admin, baz, NodeState("v-a"))
try:
    PE(user).set(user, qux, NodeState("vm-"))
except PermissionError as e:
    print(e)  # Permission denied as /baz/ is not modifiable
```