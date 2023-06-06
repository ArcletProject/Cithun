# Cithun

仿照 Linux 下的文件权限系统实现的权限管理系统。

WIP

## 特性

- 通过类似 Linux 下的文件权限系统的方式管理权限
- 支持用户组
- 支持用户组继承
- 可用上下文选择此时的权限

## Example

```python
from arclet.cithun import User, NodeState, Group, monitor, context

with context(scope="main"):
    admin = Group('admin', 100)
    monitor.add(admin, "/foo/bar/baz/", NodeState(7))
    
    user = User('cithun')
    user.join(admin)
    
    monitor.get(user, "/foo/bar/baz/")  # vma
    monitor.sadd(user, "/foo/bar/baz/qux")
    monitor.available(user, "/foo/bar/baz/qux")  # False as default perm of qux is vm-
    monitor.smodify(admin, "/foo/bar/baz/", NodeState("v-a"))
    monitor.modify(user, "/foo/bar/baz/qux", NodeState(7)) # False as /baz/ is not modifiable
```