from arclet.cithun import Group, NodeState, User, monitor, Node

bar = Node("/foo/bar/").mkdir(parents=True)
baz = (bar / "baz").mkdir()
qux = (baz / "qux").touch()

admin = Group("admin", 100)
monitor.sset(admin, baz, NodeState("vma"))

user = User("cithun")
user.join(admin)
monitor.sset(user, qux, NodeState("-ma"))

# user.get("/foo/bar/baz/")  # vma
# user.sadd("/foo/bar/baz/qux")
# user.available("/foo/bar/baz/qux")  # False as default perm of qux is vm-
# user.smodify("/foo/bar/baz/", NodeState("v-a"))
# user.modify("/foo/bar/baz/qux", NodeState(7))
print(monitor.sget(user, "/foo/bar/baz"))  # vma
print(monitor.sget(user, "/foo/bar/baz/qux"))  # -ma
print(monitor.get(user, "/foo/bar/baz/qux"))  # 7
