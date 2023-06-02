from src.arclet.cithun.node import NodeState
from src.arclet.cithun.user import User

JACK = User("jack")
JACK.set("food/fruit/apple", NodeState("vma"))
JACK.set("food/vegetable/")
print(JACK)
print(JACK.available("food/fruit/apple"))
JACK.set("food/fruit/", NodeState("v-a"))
print(JACK)
print(JACK.available("food/fruit/apple"))
print(JACK.modify("food/fruit/apple", NodeState("vm-")))
print(JACK.get("food/fruit/apple"))
