# Cithun

仿照 Linux 下的文件权限系统实现的权限管理系统。

## 特性

- 通过类似 Linux 下的文件权限系统的方式管理权限
- 支持用户组
- 支持用户组继承

## Example

```python
from arclet.cithun import Permission
from arclet.cithun.builtins import System

system = System("data.json")

with system.transaction():
    AUTH_1 = system.create_role("ROLE_AUTH_1", "AUTH_1")
    AUTH_2 = system.create_role("ROLE_AUTH_2", "AUTH_2")
    AUTH_3 = system.create_role("ROLE_AUTH_3", "AUTH_3")
    AUTH_4 = system.create_role("ROLE_AUTH_4", "AUTH_4")
    AUTH_5 = system.create_role("ROLE_AUTH_5", "AUTH_5")
    system.inherit(AUTH_2, AUTH_1)
    system.inherit(AUTH_3, AUTH_2)
    system.inherit(AUTH_4, AUTH_3)
    system.inherit(AUTH_5, AUTH_4)
    alice = system.create_user("alice", "Alice")
    bob = system.create_user("bob", "Bob")
    carol = system.create_user("carol", "Carol")
    system.inherit(alice, AUTH_1)
    system.inherit(bob, AUTH_3)
    system.inherit(carol, AUTH_5)

    system.assign(AUTH_1, "app", Permission.AVAILABLE)
    system.assign(AUTH_3, "app", Permission.VISIT)
    system.assign(AUTH_5, "app.data", Permission.AVAILABLE | Permission.VISIT | Permission.MODIFY)

    system.assign(AUTH_4, "app.secret", Permission.AVAILABLE | Permission.VISIT)
    system.assign(alice, "app.data", Permission.MODIFY)
    system.assign(bob, "app.config", Permission.MODIFY)

    system.depend(alice, "app.data", AUTH_4, "app.secret", Permission.VISIT)
    system.depend(bob, "app.config", alice, "app.data",Permission.VISIT)

```