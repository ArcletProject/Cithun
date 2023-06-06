from arclet.cithun import User, NodeState, Group, monitor

admin = Group('admin', 100)
monitor.add(admin, "/foo/bar/baz/", NodeState(7))

user = User('cithun')
user.join(admin)

monitor.get(user, "/foo/bar/baz/")  # vma
monitor.sadd(user, "/foo/bar/baz/qux")
monitor.available(user, "/foo/bar/baz/qux")  # False as default perm of qux is vm-
monitor.smodify(admin, "/foo/bar/baz/", NodeState("v-a"))
monitor.modify(user, "/foo/bar/baz/qux", NodeState(7))
