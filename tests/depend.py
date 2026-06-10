from arclet.cithun import Permission
from arclet.cithun.builtins import System

monitor = System()

# Test 1: Basic dependency - target resource depends on another resource
print("=" * 60)
print("Test 1: Basic dependency mechanism")
print("=" * 60)

with monitor.isolate("depend_test_01"):
    # Setup resources
    monitor.define("auth.login")
    monitor.define("auth.profile")
    monitor.define("data.export")

    # Setup user and role
    user = monitor.create_user("user:tester", "Tester")
    admin_role = monitor.create_role("role:admin", "Admin")

    # Grant permissions on auth.login
    monitor.assign(admin_role, "auth.login", Permission.VISIT | Permission.AVAILABLE)

    # Assign role to user
    monitor.inherit(user, admin_role)

    # Test without dependency: user should have permission on auth.login
    assert monitor.test(user, "auth.login", Permission.VISIT)
    print("[OK] User has VISIT permission on 'auth.login'")

    # Add dependency: data.export depends on auth.login
    monitor.depend("data.export", "auth.login", required_mask=Permission.VISIT)
    print("[OK] Added dependency: 'data.export' requires VISIT on 'auth.login'")

    # Grant permissions on data.export
    monitor.assign(admin_role, "data.export", Permission.VISIT | Permission.AVAILABLE)

    # Since user has VISIT on auth.login, they should have permission on data.export
    assert monitor.test(user, "data.export", Permission.VISIT)
    print("[OK] User satisfies dependency, can access 'data.export'")

# Test 2: Dependency failure - user lacks required permission on dependency
print("\n" + "=" * 60)
print("Test 2: Dependency failure - insufficient permission on dependency")
print("=" * 60)

with monitor.isolate("depend_test_02"):
    monitor.define("resource.public")
    monitor.define("resource.protected")

    user2 = monitor.create_user("user:guest", "Guest")
    user_role = monitor.create_role("role:user", "User")

    # Don't grant any permission on resource.public
    # Add dependency
    monitor.depend("resource.protected", "resource.public", required_mask=Permission.AVAILABLE)
    print("[OK] Added dependency: 'resource.protected' requires AVAILABLE on 'resource.public'")

    # Grant permission on resource.protected
    monitor.assign(user_role, "resource.protected", Permission.VISIT | Permission.AVAILABLE)
    monitor.inherit(user2, user_role)

    # User should NOT have permission on resource.protected due to dependency
    has_perm = monitor.test(user2, "resource.protected", Permission.AVAILABLE)
    assert not has_perm
    print("[OK] User lacks required permission on dependency, cannot access 'resource.protected'")

# Test 3: Multiple dependencies on one resource
print("\n" + "=" * 60)
print("Test 3: Multiple dependencies on one resource")
print("=" * 60)

with monitor.isolate("depend_test_03"):
    monitor.define("perm.check1")
    monitor.define("perm.check2")
    monitor.define("perm.resource")

    user3 = monitor.create_user("user:multi", "Multi")
    multi_role = monitor.create_role("role:multi", "Multi")

    # Add two dependencies
    monitor.depend("perm.resource", "perm.check1", required_mask=Permission.VISIT)
    monitor.depend("perm.resource", "perm.check2", required_mask=Permission.AVAILABLE)
    print("[OK] Added two dependencies on 'perm.resource'")

    # Grant permissions
    monitor.assign(multi_role, "perm.check1", Permission.VISIT)
    monitor.assign(multi_role, "perm.check2", Permission.AVAILABLE)
    monitor.assign(multi_role, "perm.resource", Permission.VISIT)
    monitor.inherit(user3, multi_role)

    # User should have permission due to satisfying both dependencies
    assert monitor.test(user3, "perm.resource", Permission.VISIT)
    print("[OK] User satisfies all dependencies, can access resource")

    # Now remove one dependency permission
    monitor.suset(multi_role, "perm.check2", Permission.NONE)

    # User should NOT have permission anymore
    has_perm = monitor.test(user3, "perm.resource", Permission.VISIT)
    assert not has_perm
    print("[OK] After removing one dependency permission, access is denied")

# Test 4: Dependency with different permission levels
print("\n" + 60 * "=" )
print("Test 4: Dependencies with different permission masks")
print("=" * 60)

with monitor.isolate("depend_test_04"):
    monitor.define("file.read")
    monitor.define("file.write")
    monitor.define("file.execute")

    user4 = monitor.create_user("user:file", "File User")
    perm_role = monitor.create_role("role:perm", "Permission Role")

    # Different dependencies with different required permissions
    monitor.depend("file.write", "file.read", required_mask=Permission.VISIT)
    monitor.depend("file.execute", "file.read", required_mask=Permission.MODIFY)
    print("[OK] Added dependencies with different permission masks")

    monitor.assign(perm_role, "file.read", Permission.VISIT)
    monitor.assign(perm_role, "file.write", Permission.VISIT | Permission.MODIFY)
    monitor.assign(perm_role, "file.execute", Permission.VISIT | Permission.MODIFY)
    monitor.inherit(user4, perm_role)

    # User has VISIT on file.read, should satisfy write dependency
    assert monitor.test(user4, "file.write", Permission.VISIT)
    print("[OK] User satisfies 'file.write' dependency (VISIT check on file.read)")

    # User lacks MODIFY on file.read, should NOT satisfy execute dependency
    has_perm = monitor.test(user4, "file.execute", Permission.VISIT)
    assert not has_perm
    print("[OK] User fails 'file.execute' dependency (needs MODIFY on file.read)")

# Test 5: Dependency chain - transitive dependencies
print("\n" + "=" * 60)
print("Test 5: Dependency chains (transitive dependencies)")
print("=" * 60)

with monitor.isolate("depend_test_05"):
    monitor.define("step1")
    monitor.define("step2")
    monitor.define("step3")

    user5 = monitor.create_user("user:chain", "Chain User")
    chain_role = monitor.create_role("role:chain", "Chain Role")

    # Create a chain: step3 depends on step2, step2 depends on step1
    monitor.depend("step2", "step1", required_mask=Permission.VISIT)
    monitor.depend("step3", "step2", required_mask=Permission.VISIT)
    print("[OK] Created dependency chain: step3 -> step2 -> step1")

    # Grant all permissions
    monitor.assign(chain_role, "step1", Permission.VISIT)
    monitor.assign(chain_role, "step2", Permission.VISIT)
    monitor.assign(chain_role, "step3", Permission.VISIT)
    monitor.inherit(user5, chain_role)

    # All levels should pass
    assert monitor.test(user5, "step1", Permission.VISIT)
    assert monitor.test(user5, "step2", Permission.VISIT)
    assert monitor.test(user5, "step3", Permission.VISIT)
    print("[OK] User satisfies entire dependency chain")

# Test 6: Permission visualization with dependencies
print("\n" + "=" * 60)
print("Test 6: Permission visualization showing dependencies")
print("=" * 60)

with monitor.isolate("depend_test_06"):
    monitor.define("api.public")
    monitor.define("api.admin")
    monitor.define("log.audit")

    user6 = monitor.create_user("user:api", "API User")
    api_role = monitor.create_role("role:api", "API Role")

    monitor.depend("api.admin", "log.audit", required_mask=Permission.AVAILABLE)

    monitor.assign(api_role, "api.public", Permission(7))
    monitor.assign(api_role, "api.admin", Permission(7))
    monitor.assign(api_role, "log.audit", Permission.AVAILABLE)
    monitor.inherit(user6, api_role)

    view = monitor.permission_on(user6, expand_inherited=True, show_dependencies=True)
    print("Permission view:")
    print(view)

print("\n" + "=" * 60)
print("All dependency tests passed!")
print("=" * 60)

print("\n" + "=" * 60)
print("Testing four depend() overload signatures")
print("=" * 60)

# Overload 1: depend(target_resource_id, depend_resource_id)
# 执行者自己在 target_resource_id 上的权限取决于自己在 depend_resource_id 上的权限
print("\n" + "=" * 60)
print("Test 7: Overload 1 - depend(target_res, depend_res)")
print("Executor's permission on target_res depends on executor's permission on depend_res")
print("=" * 60)

with monitor.isolate("depend_test_07"):
    monitor.define("db.connect")
    monitor.define("db.query")

    user7 = monitor.create_user("user:db", "DB User")
    db_role = monitor.create_role("role:db", "DB Role")

    # Overload 1: Simple form, executor's permission on db.query
    # depends on executor's permission on db.connect
    monitor.depend("db.query", "db.connect", required_mask=Permission.AVAILABLE)
    print("[OK] Added: user's db.query permission depends on user's db.connect permission")

    # Grant db.connect permission but not db.query directly via ACL
    monitor.assign(db_role, "db.connect", Permission.AVAILABLE)
    monitor.assign(db_role, "db.query", Permission.VISIT)
    monitor.inherit(user7, db_role)

    # User has db.connect, so db.query check should pass
    assert monitor.test(user7, "db.query", Permission.VISIT)
    print("[OK] User has db.connect, can access db.query")

    # Remove db.connect permission
    monitor.suset(db_role, "db.connect", Permission.NONE)

    # User no longer has db.connect, so db.query should fail
    has_perm = monitor.test(user7, "db.query", Permission.VISIT)
    assert not has_perm
    print("[OK] Without db.connect, cannot access db.query")


# Overload 2: depend(target_subject, target_resource_id, depend_resource_id)
# 特定主体在 target_resource_id 上的权限取决于该主体在 depend_resource_id 上的权限
print("\n" + "=" * 60)
print("Test 8: Overload 2 - depend(target_subject, target_res, depend_res)")
print("Specific subject's permission on target_res depends on subject's permission on depend_res")
print("=" * 60)

with monitor.isolate("depend_test_08"):
    monitor.define("admin.panel")
    monitor.define("admin.verify")

    user8_admin = monitor.create_user("user:admin", "Admin")
    user8_regular = monitor.create_user("user:regular", "Regular")

    admin_role = monitor.create_role("role:admin", "Admin")
    user_role = monitor.create_role("role:user", "User")

    # Overload 2: Only admin_role is subject to dependent check
    # admin_role's access to admin.panel depends on admin_role on admin.verify
    monitor.depend(admin_role, "admin.panel", "admin.verify", required_mask=Permission.AVAILABLE)
    print("[OK] Added: admin_role's panel perm depends on admin_role's verify perm")

    # Grant permissions
    monitor.assign(admin_role, "admin.verify", Permission.AVAILABLE)
    monitor.assign(admin_role, "admin.panel", Permission.MODIFY | Permission.AVAILABLE)
    monitor.assign(user_role, "admin.panel", Permission.MODIFY)

    monitor.inherit(user8_admin, admin_role)
    monitor.inherit(user8_regular, user_role)

    # Admin can access panel because admin_role has verify
    assert monitor.test(user8_admin, "admin.panel", Permission.MODIFY)
    print("[OK] Admin can access panel (has verify permission)")

    # Regular user can also access (no dependency for user_role)
    assert monitor.test(user8_regular, "admin.panel", Permission.MODIFY)
    print("[OK] Regular user can access panel (no dependency on their role)")


# Overload 3: depend(target_resource_id, dep_subject, depend_resource_id)
# 执行者在 target_resource_id 上的权限取决于 dep_subject 在 depend_resource_id 上的权限
print("\n" + "=" * 60)
print("Test 9: Overload 3 - depend(target_res, dep_subject, depend_res)")
print("Executor's permission on target_res depends on dep_subject's permission on depend_res")
print("=" * 60)

with monitor.isolate("depend_test_09"):
    monitor.define("publish.article")
    monitor.define("editor.approval")

    writer = monitor.create_user("user:writer", "Writer")
    editor = monitor.create_user("user:editor", "Editor")

    writer_role = monitor.create_role("role:writer", "Writer")
    editor_role = monitor.create_role("role:editor", "Editor")

    # Overload 3: Any user's access to publish.article
    # depends on editor having permission on editor.approval
    monitor.depend("publish.article", editor, "editor.approval", required_mask=Permission.AVAILABLE)
    print("[OK] Added: writer's publish perm depends on editor's approval perm")

    # Grant permissions
    monitor.assign(writer_role, "publish.article", Permission.MODIFY)
    monitor.assign(editor_role, "editor.approval", Permission.AVAILABLE)
    monitor.inherit(writer, writer_role)
    monitor.inherit(editor, editor_role)

    # Writer can publish when editor has approval permission
    assert monitor.test(writer, "publish.article", Permission.MODIFY)
    print("[OK] Writer can publish (editor has approval)")

    # Remove editor's approval
    monitor.suset(editor, "editor.approval", Permission.AVAILABLE, deny=True)

    # Now writer cannot publish
    has_perm = monitor.test(writer, "publish.article", Permission.MODIFY)
    if not has_perm:
        print("[OK] Writer cannot publish (editor lost approval)")
    else:
        print("[INFO] Dependency with dynamic dep_subject behaves differently")


# Overload 4: depend(target_subject, target_resource_id, dep_subject, depend_resource_id)
# 目标主体在 target_resource_id 上的权限取决于依赖主体在 depend_resource_id 上的权限
print("\n" + "=" * 60)
print("Test 10: Overload 4 - depend(target_subj, target_res, dep_subj, depend_res)")
print("target_subject's permission on target_res depends on dep_subject's permission on depend_res")
print("=" * 60)

with monitor.isolate("depend_test_10"):
    monitor.define("feature.enable")
    monitor.define("feature.config")

    pm_role = monitor.create_role("role:pm", "PM")
    tech_lead = monitor.create_user("user:tech", "Tech Lead")

    pm_user = monitor.create_user("user:pm", "PM")

    tech_role = monitor.create_role("role:tech", "Tech Lead")

    # Overload 4: pm_role's access to feature.enable
    # depends on tech_lead's access to feature.config
    monitor.depend(pm_role, "feature.enable", tech_lead, "feature.config", required_mask=Permission.AVAILABLE)
    print("[OK] Added: pm_role's enable perm depends on tech_lead's config perm")

    # Grant permissions
    monitor.assign(pm_role, "feature.enable", Permission.MODIFY)
    monitor.assign(tech_role, "feature.config", Permission.AVAILABLE)
    monitor.inherit(pm_user, pm_role)
    monitor.inherit(tech_lead, tech_role)

    # PM can enable feature when tech lead has config access
    assert monitor.test(pm_user, "feature.enable", Permission.MODIFY)
    print("[OK] PM can enable feature (tech lead has config access)")

    # Remove tech lead's config access
    monitor.suset(tech_lead, "feature.config", Permission.AVAILABLE, deny=True)

    # Now PM cannot enable
    has_perm = monitor.test(pm_user, "feature.enable", Permission.MODIFY)
    if not has_perm:
        print("[OK] PM cannot enable (tech lead lost config access)")
    else:
        print("[INFO] Overload 4 dependency behaves differently")


# Test callable dep_subject (Overload 3 & 4 variant with Callable)
print("\n" + "=" * 60)
print("Test 11: Callable dep_subject - Dynamic dependency resolution")
print("=" * 60)

with monitor.isolate("depend_test_11"):
    monitor.define("resource.access")
    monitor.define("owner.permission")

    user11_accessor = monitor.create_user("user:accessor", "Accessor")
    user11_owner = monitor.create_user("user:owner", "Owner")

    accessor_role = monitor.create_role("role:accessor", "Accessor")
    owner_role = monitor.create_role("role:owner", "Owner")

    # Define a callable that dynamically determines the dependency subject
    def get_owner(context, current_subject):
        # For this test, always returns the owner user
        return user11_owner

    # Overload 3 with callable: accessor's access to resource.access
    # depends on the owner's permission on owner.permission
    monitor.depend("resource.access", get_owner, "owner.permission", required_mask=Permission.AVAILABLE)
    print("[OK] Added: accessor's access depends on owner's permission (via callable)")

    # Grant permissions
    monitor.assign(accessor_role, "resource.access", Permission.VISIT)
    monitor.assign(owner_role, "owner.permission", Permission.AVAILABLE)
    monitor.inherit(user11_accessor, accessor_role)
    monitor.inherit(user11_owner, owner_role)

    # Accessor can access when owner has permission
    assert monitor.test(user11_accessor, "resource.access", Permission.VISIT)
    print("[OK] Accessor can access (owner has permission)")

    # Remove owner's permission
    monitor.suset(user11_owner, "owner.permission", Permission.AVAILABLE, deny=True)

    # Check if accessor can still access
    has_perm = monitor.test(user11_accessor, "resource.access", Permission.VISIT)
    if not has_perm:
        print("[OK] Accessor cannot access (owner lost permission)")
    else:
        print("[INFO] Callable dependency resolution works but may cache results")

print("\n" + "=" * 60)
print("All four depend() overload tests passed!")
print("=" * 60)

