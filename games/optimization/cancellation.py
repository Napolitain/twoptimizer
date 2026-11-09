"""Caller-owned cancellation shared by compilation boundaries and native solves."""

from collections.abc import Callable, Generator
from contextlib import contextmanager
from threading import Event, Thread


class Cancelled(Exception):
    """Raised when cancellation precedes a solver result that can be validated."""


class Cancellation:
    """Latch local or external requests; never reset a request between solves.

    ``checker`` must be a quick, thread-safe predicate (for example, checking a
    per-case marker file). Native interruption runs independently of incumbent
    callbacks so quiet searches remain cancellable.
    """

    def __init__(self, checker: Callable[[], bool] | None = None):
        self._checker = checker
        self._requested = Event()

    def cancel(self) -> None:
        self._requested.set()

    @property
    def requested(self) -> bool:
        if not self._requested.is_set() and self._checker is not None and self._checker():
            self.cancel()
        return self._requested.is_set()

    def checkpoint(self) -> None:
        if self.requested:
            raise Cancelled("Cancelled before a solver result was available")

    @contextmanager
    def interrupt(self, callback: Callable[[], None]) -> Generator[None]:
        """Request native interruption until it returns, then always join the watcher.

        Repeated requests close the race where CP-SAT's stop method is called
        just before its native Solve starts. A watcher error is raised after a
        normal solve return; an original solve exception keeps precedence.
        """
        self.checkpoint()
        finished = Event()
        errors: list[Exception] = []
        watcher = Thread(
            target=self._watch,
            args=(callback, finished, errors),
            name="twoptimizer-cancel",
            daemon=True,
        )
        watcher.start()
        try:
            yield
        finally:
            finished.set()
            watcher.join()
        if errors:
            raise errors[0]

    def _watch(
        self, callback: Callable[[], None], finished: Event, errors: list[Exception]
    ) -> None:
        while not finished.is_set():
            try:
                if self.requested:
                    callback()
            except Exception as error:
                # Stop native work on a failed external check too, and retry a
                # transient native interruption failure on the next poll.
                self.cancel()
                if not errors:
                    errors.append(error)
            finished.wait(0.05)
