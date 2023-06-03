from arclet.cithun.node import NodeState
from arclet.cithun import monitor, User, context

with context(scope="main"):
    JACK = User("jack")
    monitor.sadd(JACK, "food/fruit/apple", NodeState("vma"))
    monitor.sadd(JACK, "food/vegetable/")
    print(JACK)
    print(monitor.available(JACK, "food/fruit/apple"))
    monitor.smodify(JACK, "food/fruit/", NodeState("v-a"))
    print(JACK)
    print(monitor.available(JACK, "food/fruit/apple"))
    print(monitor.modify(JACK, "food/fruit/apple", NodeState("vm-")))
    print(monitor.sget(JACK, "food/fruit/apple"))
