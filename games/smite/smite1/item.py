import dataclasses

from games.smite.smite1.spells import Stats


@dataclasses.dataclass
class Item:
    name: str
    cost: float
    stats: Stats = None


@dataclasses.dataclass
class Starter(Item):
    pass


@dataclasses.dataclass
class RatatoskrAcorn(Item):
    pass


@dataclasses.dataclass
class Build:
    item1: Starter
    item2: Item
    item3: Item
    item4: Item
    item5: Item
    item6: Item


@dataclasses.dataclass
class RatatoskrBuild(Build):
    item1: RatatoskrAcorn
    item2: Starter
    item3: Item
    item4: Item
    item5: Item
    item6: Item
