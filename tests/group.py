from arclet.cithun import User, NodeState, Group

admin = Group('admin', 100)
admin.add("/foo/bar/baz/", NodeState("vma"))

user = User('cithun')
user.join(admin)

user.get("/foo/bar/baz/")  # vma
user.sadd("/foo/bar/baz/qux")
user.available("/foo/bar/baz/qux")  # False as default perm of qux is vm-
user.smodify("/foo/bar/baz/", NodeState("v-a"))
user.modify("/foo/bar/baz/qux", NodeState(7))
