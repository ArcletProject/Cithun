# Cithun

仿照 Linux 下的文件权限系统实现的权限管理系统。

WIP

## Example

```python
from arclet.cithun import User, NodeState, Group, monitor

admin = Group('admin', 100)
monitor.set(admin, "/foo/bar/baz/", NodeState(7))

user = User('cithun')
user.groups.append(admin)

monitor.get(user, "/foo/bar/baz/") # vma
monitor.suadd(user, "/foo/bar/baz/qux")
monitor.available(user, "/foo/bar/baz/qux") # False as default perm of qux is vm-
monitor.suset(user, "/foo/bar/baz/", NodeState("v-a"))
monitor.set(user, "/foo/bar/baz/qux", NodeState(7))  # False as /baz/ is not modifiable
```