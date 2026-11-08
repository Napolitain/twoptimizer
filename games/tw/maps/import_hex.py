"""Extract factual region contacts from published Rome II / Attila hex maps.

The binary field layout is documented by CampaignMapToolkit. This independent
reader supports only the two source formats used here; it does not copy the
toolkit's editor or pathfinding implementation. Contacts mean shared hex edges,
not inferred sea routes, strait crossings or certified economic-effect scope.
"""

from dataclasses import dataclass
from struct import unpack_from
from zlib import crc32

import numpy as np


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.position = 0

    def take(self, size: int) -> bytes:
        end = self.position + size
        if size < 0 or end > len(self.data):
            raise ValueError("Truncated hex map")
        value = self.data[self.position : end]
        self.position = end
        return value

    def integer(self) -> int:
        return unpack_from("<I", self.take(4))[0]

    def string(self) -> str:
        return self.take(self.integer()).decode("ascii")

    def strings(self) -> tuple[str, ...]:
        count = self.integer()
        if count > 10000:
            raise ValueError("Invalid hex map string count")
        return tuple(self.string() for _ in range(count))


@dataclass(frozen=True, slots=True)
class HexMap:
    game: str
    campaign: str
    version: int
    width: int
    height: int
    land_regions: tuple[str, ...]
    sea_regions: tuple[str, ...]
    cells: bytes

    def arrays(self):
        stride = 8 if self.version == 13 else 16
        raw = np.frombuffer(self.cells, dtype=np.uint8).reshape(self.height, self.width, stride)
        region = (raw[:, :, 1].astype(np.int32) << 5) + (raw[:, :, 0] >> 3) - 1
        sea = (raw[:, :, 0] & 3) == 1
        passable = (raw[:, :, 2] & 8) == 0
        return region, sea, passable


def parse_hex(data: bytes) -> HexMap:
    if len(data) < 12 or crc32(data[:-4]) != unpack_from("<I", data, len(data) - 4)[0]:
        raise ValueError("Hex map CRC32 mismatch")
    source = Reader(data[:-4])
    major, minor = source.integer(), source.integer()
    if major != 0 or minor not in {13, 15}:
        raise ValueError(f"Unsupported hex map version: {major}/{minor}")
    game, campaign = source.string(), source.string()
    land, sea = source.strings(), source.strings()
    if len(set(land)) != len(land) or len(set(sea)) != len(sea) or set(land) & set(sea):
        raise ValueError("Duplicate hex map region keys")
    for _ in range(4):
        source.strings()  # Ground types, climates and attrition identifiers.
    for _ in range(2):
        source.take(source.integer() * 4)  # Display colour palettes.
    width, height = source.integer(), source.integer()
    if not 0 < width <= 4096 or not 0 < height <= 4096:
        raise ValueError("Invalid hex map dimensions")
    cells = source.take(width * height * (8 if minor == 13 else 16))
    if source.position != len(source.data):
        raise ValueError("Unexpected trailing hex map data")
    result = HexMap(game, campaign, minor, width, height, land, sea, cells)
    ids, sea_cells, _ = result.arrays()
    if np.any(ids >= len(land) + len(sea)):
        raise ValueError("Hex cell refers to an unknown region")
    if np.any((ids >= 0) & (sea_cells != (ids >= len(land)))):
        raise ValueError("Hex cell terrain disagrees with its region type")
    return result


def _edge_slices(width: int):
    """Three undirected edges of each flat-top, odd-column-offset hex cell."""
    yield (slice(None, -1), slice(None)), (slice(1, None), slice(None))
    yield (slice(None), slice(None, -1)), (slice(None), slice(1, None))
    for parity, rows in (
        (0, (slice(1, None), slice(None, -1))),
        (1, (slice(None, -1), slice(1, None))),
    ):
        yield (rows[0], slice(parity, width - 1, 2)), (rows[1], slice(parity + 1, width, 2))


def _pairs(left, right, accepted):
    selected = np.column_stack((left[accepted], right[accepted]))
    return {tuple(pair) for pair in np.unique(np.sort(selected, axis=1), axis=0).tolist()}


def extract_contacts(model: HexMap, excluded: tuple[str, ...] = ()) -> dict:
    """Return separate geometric, passable-land, sea and coastal contact graphs."""
    region, sea, passable = model.arrays()
    names = model.land_regions + model.sea_regions
    combined = region
    allowed = (region >= 0) & ~np.isin(combined, [names.index(key) for key in excluded])
    edges = {key: set() for key in ("land", "passable_land", "sea", "coastal")}
    for a, b in _edge_slices(model.width):
        accepted = allowed[a] & allowed[b] & (combined[a] != combined[b])
        land = ~sea[a] & ~sea[b]
        masks = {
            "land": land,
            "passable_land": land & passable[a] & passable[b],
            "sea": sea[a] & sea[b],
            "coastal": sea[a] != sea[b],
        }
        for kind, mask in masks.items():
            edges[kind].update(_pairs(combined[a], combined[b], accepted & mask))
    return {
        kind: sorted(sorted((names[left], names[right])) for left, right in pairs)
        for kind, pairs in edges.items()
    }


def region_centroids(model: HexMap) -> dict[str, tuple[float, float]]:
    """Return territory centres in native column/offset-row coordinates."""
    region, _, _ = model.arrays()
    names = model.land_regions + model.sea_regions
    rows, columns = np.indices(region.shape)
    valid = region >= 0
    counts = np.bincount(region[valid], minlength=len(names))
    x_sum = np.bincount(region[valid], weights=columns[valid], minlength=len(names))
    y_sum = np.bincount(
        region[valid], weights=(rows + (columns % 2) / 2)[valid], minlength=len(names)
    )
    return {
        name: (round(float(x_sum[index] / count), 4), round(float(y_sum[index] / count), 4))
        for index, (name, count) in enumerate(zip(names, counts, strict=True))
        if count
    }
