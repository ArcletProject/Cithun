from arclet.cithun.node import Node, ROOT, mkdir, INDEX_MAP
from pprint import pprint

FOOD = mkdir("food")
FRUIT = FOOD.mkdir("fruit")
VEGETABLE = FOOD.mkdir("vegetable")
APPLE = FRUIT.touch("apple")
BANANA = FRUIT.touch("banana")
SMALL_TOMATO = VEGETABLE.touch("tomato/small tomato", parents=True)

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

pprint(INDEX_MAP)
#
# FRUIT.move(VEGETABLE)
# print("=============================")
# pprint(NODE_CHILD_MAP[FOOD])
# pprint(NODE_CHILD_MAP[VEGETABLE])
#
# """
# /
# └── food
#     └── vegetable
#         ├── fruit
#         │   ├── apple
#         │   └── banana
#         └── tomato
#             └── small tomato
# """
