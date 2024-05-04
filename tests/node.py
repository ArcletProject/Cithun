from pprint import pprint

from arclet.cithun.node import CHILD_MAP, INDEX_MAP, mkdir

FOOD = mkdir("food")
FRUIT = (FOOD / "fruit").mkdir()
VEGETABLE = (FOOD / "vegetable").mkdir()
APPLE = (FRUIT / "apple").touch()
BANANA = (FRUIT / "banana").touch()
SMALL_TOMATO = (VEGETABLE / "tomato" / "small tomato").mkdir(parents=True)
print(SMALL_TOMATO.dot())
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
pprint(CHILD_MAP)
