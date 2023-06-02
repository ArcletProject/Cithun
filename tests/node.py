from src.arclet.cithun.node import Node, ROOT, NODE_CHILD_MAP
from pprint import pprint

FOOD = Node("food", isdir=True)
FRUIT = Node("fruit", FOOD, isdir=True)
VEGETABLE = Node("vegetable", FOOD, isdir=True)
APPLE = Node("apple", FRUIT)
BANANA = Node("banana", FRUIT)
TOMATO = Node("tomato", VEGETABLE, isdir=True)
SMALL_TOMATO = Node("small tomato", TOMATO)

print(ROOT)
print(FOOD)
print(FRUIT)
print(VEGETABLE)
print(APPLE)
print(BANANA)
print(TOMATO)
pprint(NODE_CHILD_MAP[FOOD])

FRUIT.move(VEGETABLE)
print("=============================")
pprint(NODE_CHILD_MAP[FOOD])

try:
    Node("")
except ValueError as e:
    print(e)

print(FOOD.get("./vegetable"))
assert Node.from_path("./vegetable/", FOOD) == VEGETABLE
assert Node.from_path("./vegetable", FOOD) != VEGETABLE
