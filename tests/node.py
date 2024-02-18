from arclet.cithun.node import Node, ROOT, NODE_CHILD_MAP, Selector
from pprint import pprint

FOOD = Node("food", isdir=True)
FRUIT = FOOD / "fruit/"
VEGETABLE = Node("vegetable", FOOD, isdir=True)
APPLE = Node("apple", FRUIT)
BANANA = Node("banana", FRUIT)
SMALL_TOMATO = VEGETABLE / "tomato" / "small tomato"

"""
# NodeTree
/
└── food
    ├── fruit
    │   ├── apple
    │   └── banana
    └── vegetable
        └── tomato
            └── small tomato
"""

print(ROOT)
print(FOOD)
print(FRUIT)
print(VEGETABLE)
print(APPLE)
print(BANANA)
print(SMALL_TOMATO)
pprint(NODE_CHILD_MAP[FOOD])

FRUIT.move(VEGETABLE)
print("=============================")
pprint(NODE_CHILD_MAP[FOOD])
pprint(NODE_CHILD_MAP[VEGETABLE])

"""
/
└── food
    └── vegetable
        ├── fruit
        │   ├── apple
        │   └── banana
        └── tomato
            └── small tomato
"""

try:
    Node("")
except ValueError as e:
    print(e)

print(FOOD.get("./vegetable"))
print(ROOT.get("/food/vegetable/tomato/small tomato"))
print(ROOT.get("/food/vegetable/tomato/small tomato/"))
