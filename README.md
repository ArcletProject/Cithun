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
from arclet.cithun import User, NodeState, Group, context

with context(scope="main"):
    admin = Group('admin', 100)
    admin.add("/foo/bar/baz/", NodeState("vma"))
    
    user = User('cithun')
    user.join(admin)
    
    user.get("/foo/bar/baz/")  # vma
    user.sadd("/foo/bar/baz/qux")
    user.available("/foo/bar/baz/qux")  # False as default perm of qux is vm-
    admin.smodify("/foo/bar/baz/", NodeState("v-a"))
    user.modify("/foo/bar/baz/qux", NodeState(7)) # False as /baz/ is not modifiable
```