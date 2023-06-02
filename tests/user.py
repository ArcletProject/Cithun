from arclet.cithun.node import NodeState
from arclet.cithun.user import User

JACK = User("jack")
JACK.suadd("food/fruit/apple", NodeState("vma"))
JACK.suadd("food/vegetable/")
print(JACK)
print(JACK.available("food/fruit/apple"))
JACK.suset("food/fruit/", NodeState("v-a"))
print(JACK)
print(JACK.available("food/fruit/apple"))
print(JACK.set("food/fruit/apple", NodeState("vm-")))
print(JACK.suget("food/fruit/apple"))
