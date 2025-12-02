# Cithun

仿照 Linux 下的文件权限系统实现的权限管理系统。

WIP

## 特性

- 通过类似 Linux 下的文件权限系统的方式管理权限
- 支持用户组
- 支持用户组继承

## Example
storage = InMemoryStorage()

    # 定义角色
    # for i in range(1, 6):
    #     rid = f"ROLE_AUTH_{i}"
    #     storage.add_role(Role(id=rid, name=f"AUTH_{i}"))
    #     if i > 1:
    #         storage.inherit(f"ROLE_AUTH_{i}", f"ROLE_AUTH_{i-1}")
    AUTH_1 = Role(id="ROLE_AUTH_1", name="AUTH_1")
    AUTH_2 = Role(id="ROLE_AUTH_2", name="AUTH_2")
    AUTH_3 = Role(id="ROLE_AUTH_3", name="AUTH_3")
    AUTH_4 = Role(id="ROLE_AUTH_4", name="AUTH_4")
    AUTH_5 = Role(id="ROLE_AUTH_5", name="AUTH_5")
    auths = [AUTH_1, AUTH_2, AUTH_3, AUTH_4, AUTH_5]
    for role in auths:
        storage.add_role(role)
    for i in range(2, 6):
        storage.inherit(auths[i-1], auths[i-2])

    # 定义用户
    alice = User(id="alice", name="Alice", role_ids=[AUTH_1.id])
    bob = User(id="bob", name="Bob", role_ids=[AUTH_3.id])
    carol = User(id="carol", name="Carol", role_ids=[AUTH_5.id])
    storage.add_user(alice)
    storage.add_user(bob)
    storage.add_user(carol)

    # ACL 配置
    storage.assign(AUTH_1, "app", Permission.AVAILABLE)
    storage.assign(AUTH_3, "app", Permission.VISIT)
    storage.assign(AUTH_4, "app/secret", Permission.VISIT)

    # Alice 依赖
    alice_data = storage.assign(alice, "app/data", Permission.MODIFY)
    storage.depend(alice_data, AUTH_4, "app/secret", Permission.VISIT)

    # Bob 依赖
    bob_config = storage.assign(bob, "app/config", Permission.MODIFY)
    storage.depend(bob_config, alice, "app/data", Permission.VISIT)
    # Carol 权限
    storage.assign(AUTH_5, "app/data", Permission.AVAILABLE | Permission.VISIT | Permission.MODIFY)
    storage.assign(AUTH_4, "app/secret", Permission.AVAILABLE | Permission.VISIT)

    # Engine
    engine = PermissionEngine()
    engine.register_strategy(ExampleProjectOwnerStrategy())
    service = PermissionService(storage, engine)

    ctx = RequestContext(time=datetime.datetime.utcnow())

    def print_perms(subject: User | Role, res_id: str, label: str):
        subject_id = subject.id
        if isinstance(subject, User):
            mask = service.get_effective_permissions(subject, res_id, ctx)
        else:
            mask = service._calc_permissions_for_subject(
                SubjectType.ROLE, subject, storage.get_resource(res_id), ctx, visited=set()
            )
        print(f"[{label}] {subject.__class__.__name__}={subject_id} on {res_id} => {Permission(mask)!r}")

    print_perms(alice, "app", "alice on app")
    print_perms(bob, "app", "bob on app")
    print_perms(carol, "app", "carol on app")
    print_perms(AUTH_4, "app/secret", "role_auth_4 on app/secret")
    print_perms(alice, "app/data", "alice on app/data (depends on role4@secret)")
    print_perms(bob, "app/config", "bob on app/config (depends on alice@app/data)")
    print_perms(carol, "app/data", "carol on app/data (auth5 full)")

    print("alice can MODIFY app/data?", service.has_permission(alice, "app/data", Permission.MODIFY, ctx))
    print("bob can MODIFY app/config?", service.has_permission(bob, "app/config", Permission.MODIFY, ctx))

    # Dynamic permission via strategy
    storage.assign(alice, "app/data", Permission.VISIT)
    print_perms(alice, "app/data", "alice on app/data (new permission)")
    print("bob can MODIFY app/config now?", service.has_permission(bob, "app/config", Permission.MODIFY, ctx))

```python
from arclet.cithun import Permission
from arclet.cithun.builtins import System

system = System()

with system.transaction():
    AUTH_1 = system.create_role("ROLE_AUTH_1", "AUTH_1")
    AUTH_2 = system.create_role("ROLE_AUTH_2", "AUTH_2")
    AUTH_3 = system.create_role("ROLE_AUTH_3", "AUTH_3")
    AUTH_4 = system.create_role("ROLE_AUTH_4", "AUTH_4")
    AUTH_5 = system.create_role("ROLE_AUTH_5", "AUTH_5")
    system.inherit_role(AUTH_2, AUTH_1)
    system.inherit_role(AUTH_3, AUTH_2)
    system.inherit_role(AUTH_4, AUTH_3)
    system.inherit_role(AUTH_5, AUTH_4)
    alice = system.create_user("alice", "Alice", role_ids=[AUTH_1.id])
    bob = system.create_user("bob", "Bob", role_ids=[AUTH_3.id])
    carol = system.create_user("carol", "Carol", role_ids=[AUTH_5.id])

    system.assign(AUTH_1, "app", Permission.AVAILABLE)
    system.assign(AUTH_3, "app", Permission.VISIT)
    system.assign(AUTH_5, "app/data", Permission.AVAILABLE | Permission.VISIT | Permission.MODIFY)

    system.assign(AUTH_4, "app/secret", Permission.AVAILABLE | Permission.VISIT)
    system.assign(alice, "app/data", Permission.MODIFY)
    system.assign(bob, "app/config", Permission.MODIFY)

    system.depend(alice, "app/data", AUTH_4, "app/secret", Permission.VISIT)
    system.depend(bob, "app/config", alice, "app/data",Permission.VISIT)

```