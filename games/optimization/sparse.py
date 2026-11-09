"""Compressed constraint rows; exact solvers never allocate a dense matrix."""

import numpy as np


class SparseConstraints:
    def __init__(self, rows, columns):
        indices, values, pointers = [], [], [0]
        for row_indices, coefficients in rows:
            merged = {}
            for index, value in zip(row_indices, coefficients, strict=True):
                merged[index] = merged.get(index, 0.0) + value
            for index, value in sorted(merged.items()):
                if value:
                    indices.append(index)
                    values.append(value)
            pointers.append(len(indices))
        self.indices = np.asarray(indices, dtype=np.int64)
        self.values = np.asarray(values, dtype=float)
        self.pointers = np.asarray(pointers, dtype=np.int64)
        self.shape = (len(pointers) - 1, columns)
        self.row_ids = np.repeat(np.arange(self.shape[0]), np.diff(self.pointers))

    @property
    def nbytes(self):
        return sum(a.nbytes for a in (self.indices, self.values, self.pointers, self.row_ids))

    def rows(self):
        for start, end in zip(self.pointers[:-1], self.pointers[1:], strict=True):
            yield self.indices[start:end], self.values[start:end]

    def __matmul__(self, values):
        values = np.asarray(values)
        if values.ndim != 1:
            return self.toarray() @ values
        if values.shape[0] != self.shape[1]:
            raise ValueError("Constraint vector has the wrong length")
        return np.bincount(
            self.row_ids,
            weights=self.values * values[self.indices],
            minlength=self.shape[0],
        )

    def __getitem__(self, key):
        # Local-search column updates stay sparse too. Beam search explicitly
        # requests a reordered dense matrix; its small-model behavior is retained.
        if (
            isinstance(key, tuple)
            and key[0] == slice(None)
            and isinstance(key[1], (int, np.integer))
        ):
            column = int(key[1])
            if column < 0:
                column += self.shape[1]
            if not 0 <= column < self.shape[1]:
                raise IndexError("Constraint column out of range")
            selected = self.indices == column
            return np.bincount(
                self.row_ids[selected],
                weights=self.values[selected],
                minlength=self.shape[0],
            )
        if isinstance(key, (int, np.integer)):
            key = int(key)
            if key < 0:
                key += self.shape[0]
            if not 0 <= key < self.shape[0]:
                raise IndexError("Constraint row out of range")
            row = np.zeros(self.shape[1])
            start, end = self.pointers[key], self.pointers[key + 1]
            row[self.indices[start:end]] = self.values[start:end]
            return row
        return self.toarray()[key]

    def __iter__(self):
        for i in range(self.shape[0]):
            yield self[i]

    def toarray(self):
        dense = np.zeros(self.shape)
        dense[self.row_ids, self.indices] = self.values
        return dense

    def __array__(self, dtype=None, copy=None):
        if copy is False:
            raise ValueError("A sparse matrix cannot expose a dense view without copying")
        dense = self.toarray()
        return dense if dtype is None else dense.astype(dtype, copy=False)

    def update_hash(self, digest):
        """Preserve historical dense matrix fingerprints without allocating it."""
        row = np.zeros(self.shape[1])
        for indices, values in self.rows():
            row.fill(0)
            row[indices] = values
            digest.update(row.tobytes())
