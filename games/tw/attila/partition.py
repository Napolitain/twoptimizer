"""Partition a compact relaxation without assuming which game effects are global.

Only original reference rows whose decisions have known, different province
owners may be removed. Every economic definition remains in the native graph,
so a cross-province tax, product or logical condition still joins its recipients.
The full model is never modified. This module performs no native search.
"""

from collections import defaultdict
from dataclasses import dataclass

from games.optimization.native_model import constraint_variables, objective_terms


class UnsupportedPartition(ValueError):
    """The supplied builder cannot be partitioned with certified ownership."""


@dataclass(frozen=True, slots=True)
class Part:
    indices: tuple[int, ...]
    rows: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Partition:
    parts: tuple[Part, ...]
    fixed: dict[int, int]
    relaxed_rows: tuple[int, ...]
    relaxed_reference_rows: tuple[int, ...]
    constant_rows: tuple[int, ...]
    constant: int


def _index(value, size):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < size:
        raise UnsupportedPartition("Unknown variable or constraint index")
    return value


def _domains(proto):
    domains = []
    for variable in proto.variables:
        domain = tuple(variable.domain)
        if not domain or len(domain) % 2:
            raise UnsupportedPartition("Native variable domain needs nonempty interval pairs")
        intervals = tuple(zip(domain[::2], domain[1::2], strict=True))
        if any(lower > upper for lower, upper in intervals) or any(
            intervals[i][1] >= intervals[i + 1][0] for i in range(len(intervals) - 1)
        ):
            raise UnsupportedPartition("Native variable domain intervals are invalid")
        domains.append(intervals)
    return domains


def _fixed(builder, domains):
    fixed = {
        index: intervals[0][0]
        for index, intervals in enumerate(domains)
        if len(intervals) == 1 and intervals[0][0] == intervals[0][1]
    }
    for original, value in builder.fixed.items():
        _index(original, len(builder.reference.names))
        if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1):
            raise UnsupportedPartition("Reference fixed values must be binary integers")
        if original not in builder.variables:
            raise UnsupportedPartition("A fixed reference variable is missing from the builder")
        index = _index(builder.variables[original].index, len(domains))
        if not any(lower <= value <= upper for lower, upper in domains[index]):
            raise UnsupportedPartition("Reference fixed value contradicts its native domain")
        fixed[index] = value
    return fixed


class _Ownership:
    def __init__(self, builder):
        self.builder = builder
        self.cache = {}
        self.visiting = set()
        economy = builder.plan.economy
        for name, building in economy.by_id.items():
            alias = builder.plan.aliases.get(name, name)
            index = builder.indices.get(alias)
            owner = economy.owner.get(building.region.name)
            if index is not None:
                self.cache[index] = None if owner is None else frozenset((owner,))

    def owners(self, index):
        _index(index, len(self.builder.reference.names))
        if index in self.builder.fixed:
            return frozenset()
        if index in self.cache:
            return self.cache[index]
        if index in self.visiting:
            return None
        self.visiting.add(index)
        result = self._auxiliary(index)
        self.visiting.remove(index)
        self.cache[index] = result
        return result

    def _auxiliary(self, index):
        if index in self.builder.products:
            return self._union(self.builder.products[index])
        name = self.builder.reference.names[index]
        indicator = self.builder.plan.economy.logic.get(name)
        if indicator is None:
            return None
        indices = []
        for term, coefficient in indicator.expression.items():
            if coefficient:
                for name in term:
                    alias = self.builder.plan.aliases.get(name, name)
                    if alias not in self.builder.indices:
                        return None
                    indices.append(self.builder.indices[alias])
        return self._union(indices)

    def _union(self, indices):
        combined = set()
        for index in indices:
            owners = self.owners(index)
            if owners is None:
                return None
            combined.update(owners)
        return frozenset(combined)

    def crosses(self, indices):
        owners = self._union(indices)
        return owners is not None and len(owners) > 1


def _relaxed(builder, native_supports, fixed):
    ownership = _Ownership(builder)
    relaxed, originals, seen = set(), [], set()
    count = len(builder.reference.lower)
    for original, rows in builder.row_constraints.items():
        _index(original, count)
        if original not in builder.row_supports or original in builder.plan.definition_rows:
            raise UnsupportedPartition(
                "Reference row metadata is missing or names an AND definition"
            )
        supports = builder.row_supports[original]
        expected = _mapped_support(builder, supports)
        for row in rows:
            _index(row, len(native_supports))
            native = builder.model.proto.constraints[row]
            constant = not supports and native_supports[row] <= fixed.keys()
            if row in seen or native.enforcement_literal:
                raise UnsupportedPartition(
                    "Reference row metadata must name distinct plain linear rows"
                )
            if not native.has_linear() and not (constant and native.has_bool_or()):
                raise UnsupportedPartition(
                    "Reference row needs a linear or fixed Boolean constraint"
                )
            if not constant and not native_supports[row] <= expected:
                raise UnsupportedPartition("Native reference row has unexpected variables")
            seen.add(row)
        if not _mentions_logic(builder, supports) and ownership.crosses(supports):
            relaxed.update(rows)
            originals.append(original)
    return tuple(sorted(relaxed)), tuple(sorted(originals))


def _mapped_support(builder, supports):
    expected = set()
    for index in supports:
        _index(index, len(builder.reference.names))
        if index not in builder.variables:
            raise UnsupportedPartition("A reference row variable is missing from the builder")
        expected.add(_index(builder.variables[index].index, len(builder.model.proto.variables)))
    return expected


def _mentions_logic(builder, supports):
    # Indicator definitions are compiled as ordinary reference linear rows.
    # Preserve every row mentioning an indicator, rather than guessing which
    # rows define it and which merely impose a scenario requirement on it.
    logic = builder.plan.economy.logic
    return any(builder.reference.names[index] in logic for index in supports)


def _root(parents, index):
    while parents[index] != index:
        parents[index] = parents[parents[index]]
        index = parents[index]
    return index


def _components(supports, fixed, relaxed, size):
    parents = {index: index for index in range(size) if index not in fixed}
    retained = {}
    constants = []
    for row, support in enumerate(supports):
        if row in relaxed:
            continue
        active = tuple(sorted(support - fixed.keys()))
        if active:
            retained[row] = active
            first, *others = active
            for index in others:
                parents[_root(parents, index)] = _root(parents, first)
        else:
            constants.append(row)
    groups, rows = defaultdict(list), defaultdict(list)
    for index in parents:
        groups[_root(parents, index)].append(index)
    for row, active in retained.items():
        rows[_root(parents, active[0])].append(row)
    parts = [Part(tuple(indices), tuple(rows[root])) for root, indices in groups.items()]
    if constants:
        first = parts[0] if parts else Part((), ())
        replacement = Part(first.indices, tuple(sorted((*first.rows, *constants))))
        parts[:1] = [replacement]
    return tuple(parts), tuple(constants)


def partition(builder) -> Partition:
    """Return exact components after removing only certified reference cross-rows.

    Every unfixed variable and retained constraint belongs to exactly one part.
    Fixed-only constraints accompany the first part (an empty-variable part if
    necessary), so even a false constant constraint is preserved. Component
    objectives exclude fixed contributions, which are included in ``constant``
    exactly once together with the original maximization objective offset.
    Unknown reference ownership retains its row conservatively.
    """
    proto = builder.model.proto
    domains = _domains(proto)
    coefficients, offset = objective_terms(builder.model)
    fixed = _fixed(builder, domains)
    supports = [constraint_variables(row, len(domains)) for row in proto.constraints]
    relaxed, originals = _relaxed(builder, supports, fixed)
    parts, constants = _components(supports, fixed, frozenset(relaxed), len(domains))
    constant = offset + sum(coefficients.get(index, 0) * value for index, value in fixed.items())
    return Partition(parts, fixed, relaxed, originals, constants, constant)
