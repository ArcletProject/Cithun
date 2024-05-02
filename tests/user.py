from arclet.cithun import User, context
from arclet.cithun.node import NodeState

with context(scope="main"):
    JACK = User("jack")
    JACK.sadd("food/fruit/apple", NodeState("vma"))
    JACK.sadd("food/vegetable/")
    print(JACK)
    print(JACK.available("food/fruit/apple"))
    JACK.smodify("food/fruit/", NodeState("v-a"))
    print(JACK)
    print(JACK.available("food/fruit/apple"))
    print(JACK.modify("food/fruit/apple", NodeState("vm-")))
    print(JACK.sget("food/fruit/apple"))
