from pprint import pprint

from arclet.cithun.node import INDEX_MAP, mkdir

FOOD = mkdir("food")
FRUIT = (FOOD / "fruit").mkdir()
VEGETABLE = (FOOD / "vegetable").mkdir()
APPLE = (FRUIT / "apple").touch()
BANANA = (FRUIT / "banana").touch()
SMALL_TOMATO = (VEGETABLE / "tomato " / "small tomato").mkdir(parents=True)

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
