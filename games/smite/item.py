import dataclasses


@dataclasses.dataclass
class Item:
    name: str


@dataclasses.dataclass
class Starter(Item):
    pass


@dataclasses.dataclass
class Build:
    item1: Starter
    item2: Item
    item3: Item
    item4: Item
    item5: Item
    item6: Item
