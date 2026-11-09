"""Attempt deliberate invalid writes without disguising production types as mutable."""

import operator
from typing import Any


def set_item(target: Any, key: Any, value: Any) -> None:
    operator.setitem(target, key, value)


def set_attribute(target: Any, name: str, value: Any) -> None:
    setattr(target, name, value)
