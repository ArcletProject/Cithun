# Cithun

仿照 Linux 下的文件权限系统实现的权限管理系统。

WIP

## Example

```python
from arclet.cithun import User, Group, NodeState

admin = Group('admin')
admin.set("/foo/bar/baz/", NodeState(7))

user = User('cithun')
user.join(admin)

user.get("/foo/bar/baz/") # vma
user.suset("/foo/bar/baz/qux")
user.available("/foo/bar/baz/qux") # False as default perm of qux is vm-
user.suset("/foo/bar/baz/", NodeState("v-a"))
user.set("/foo/bar/baz/qux", NodeState(7))  # False as failed
```