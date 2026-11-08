"""Small independent Attila arithmetic examples."""

from games.tw.building import Building
from games.tw.enums import Scope
from games.tw.province import Province


def building(region, name, *effects, upkeep=0):
    b = Building(name, context=region.context)
    b.region = region
    b.metadata = {"metadata": {"upkeep": upkeep}}
    for key, scope, value in effects:
        b.add_effect("att_effect_" + key, Scope.REGION, value, raw_scope=scope)
    region.buildings.append(b)
    return b


def province(name, *regions):
    p = Province(name, context=regions[0].context)
    for region in regions:
        p.add_region(region)
    return p
