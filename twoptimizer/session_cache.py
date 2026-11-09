"""Bounded insertion-order retention shared by game-owned session caches."""


def trim_cache[K, V](values: dict[K, V], limit: int) -> None:
    while len(values) > limit:
        values.pop(next(iter(values)))
