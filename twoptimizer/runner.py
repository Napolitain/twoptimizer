"""Asynchronous subprocess lifetime, including cancellation and terminal exit."""

import asyncio
import json
import os
import sys
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

from twoptimizer.errors import deserialize_error
from twoptimizer.models import CaseResult, RunConfig
from twoptimizer.presentation import search_summary
from twoptimizer.progress import PREFIX, ModelStats, SearchStats, decode_progress


class CaseRunner:
    def __init__(self):
        self.process = None
        self.cancelled = False
        self._forced_stop = False
        self._cancel_path: Path | None = None

    async def request_stop(self):
        """Stop scheduling cases and let the active solver return its best result."""
        self.cancelled = True
        if self._cancel_path is not None:
            self._cancel_path.touch(exist_ok=True)

    async def stop(self):
        """Force termination when quitting or abandoning a cooperative stop."""
        self.cancelled = True
        self._forced_stop = True
        await self._reap_process()

    @contextmanager
    def _case_paths(self, config: RunConfig) -> Generator[tuple[Path, Path, Path]]:
        with TemporaryDirectory(prefix="twoptimizer-") as directory:
            request, result, cancel = (
                Path(directory) / name for name in ("request.json", "result.json", "cancel")
            )
            request.write_text(json.dumps(config.to_dict()))
            self._cancel_path = cancel
            try:
                yield request, result, cancel
            finally:
                self._cancel_path = None

    async def _reap_process(self):
        process = self.process
        if process is not None and process.returncode is None:
            with suppress(ProcessLookupError):
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 2)
            except TimeoutError:
                with suppress(ProcessLookupError):
                    process.kill()
                await process.wait()

    async def _read_output(self, process, on_log, on_progress, started, case_id=None):
        startup_seconds = None
        if process.stdout is None:
            raise RuntimeError("Solver worker output pipe is unavailable")
        async for line in process.stdout:
            text = line.decode(errors="replace").rstrip()
            if text.startswith(PREFIX):
                record = json.loads(text[len(PREFIX) :])
                if "completed" in record:
                    if record["completed"] != case_id:
                        raise RuntimeError("Solver worker returned an unexpected case ID")
                    return startup_seconds
                if startup_seconds is None:
                    startup_seconds = perf_counter() - started
                _report_progress(record, on_log, on_progress)
            elif text:
                on_log(text[:1000])
        if case_id is not None and not self._forced_stop:
            raise RuntimeError("Solver worker exited before completing the case; see the log.")
        return startup_seconds

    async def run(self, config: RunConfig, on_log, on_progress=None):
        if self.cancelled:
            return None
        started = perf_counter()
        startup_seconds = None
        with self._case_paths(config) as (request_path, result_path, cancel_path):
            process = self.process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "twoptimizer.worker",
                str(request_path),
                str(result_path),
                str(cancel_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            try:
                if self._forced_stop:
                    await self.stop()
                startup_seconds = await self._read_output(process, on_log, on_progress, started)
                await process.wait()
                if self._forced_stop:
                    return None
                if not result_path.exists():
                    raise RuntimeError(
                        f"Solver worker exited with code {process.returncode}; see the log."
                    )
                result: dict[str, Any] = json.loads(result_path.read_text())
                if not isinstance(result, dict):
                    raise RuntimeError("Solver worker returned an invalid result object")
                if "error" in result:
                    raise deserialize_error(result)
                if process.returncode:
                    raise RuntimeError(f"Solver worker exited with code {process.returncode}.")
                result = _decode_result(result, cancelled=self.cancelled)
                result["timings"].update(worker_wall_seconds=perf_counter() - started)
                if startup_seconds is not None:
                    result["timings"]["worker_startup_seconds"] = startup_seconds
                return result
            finally:
                if process.returncode is None:
                    await self.stop()


class BatchRunner(CaseRunner):
    """One worker per sequential batch; each case owns a fresh engine model."""

    def __init__(self):
        super().__init__()
        self._active = False
        self._case_id = 0

    async def _close_process(self):
        process = self.process
        if process is not None and process.stdin is not None:
            process.stdin.close()
        await self._reap_process()
        if process is not None and process.stdin is not None:
            with suppress(BrokenPipeError, ConnectionResetError):
                await process.stdin.wait_closed()

    async def stop(self):
        self.cancelled = True
        self._forced_stop = True
        await self._close_process()

    async def _ensure_process(self):
        if self.process is None or self.process.returncode is not None:
            self.process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "twoptimizer.worker",
                "--batch",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        return self.process

    async def _exchange(self, config, on_log, on_progress, started):
        with self._case_paths(config) as (request_path, result_path, cancel_path):
            try:
                process = await self._ensure_process()
                if self.cancelled:
                    return None
                if process.stdin is None:
                    raise RuntimeError("Solver worker input pipe is unavailable")
                self._case_id += 1
                request = {
                    "id": self._case_id,
                    "request": str(request_path),
                    "output": str(result_path),
                    "cancel": str(cancel_path),
                }
                process.stdin.write((json.dumps(request) + "\n").encode())
                await process.stdin.drain()
                startup = await self._read_output(
                    process, on_log, on_progress, started, self._case_id
                )
                if self._forced_stop:
                    return None
                payload = _read_batch_result(result_path, cancelled=self.cancelled)
                return payload, startup
            except BaseException as error:
                await self._close_process()
                if self._forced_stop and isinstance(error, Exception):
                    return None
                raise
            finally:
                if self.cancelled:
                    await self._close_process()

    async def run(self, config: RunConfig, on_log, on_progress=None):
        if self.cancelled:
            return None
        if self._active:
            raise RuntimeError("A batch worker can run only one case at a time")
        self._active = True
        launched = self.process is None or self.process.returncode is not None
        started = perf_counter()
        try:
            completed = await self._exchange(config, on_log, on_progress, started)
            if completed is None or self._forced_stop:
                return None
            result, startup = completed
            if "error" in result:
                raise deserialize_error(result)
            result["timings"]["worker_wall_seconds"] = perf_counter() - started
            if startup is not None:
                key = "worker_startup_seconds" if launched else "worker_dispatch_seconds"
                result["timings"][key] = startup
            return result
        finally:
            self._active = False


def _read_batch_result(path: Path, *, cancelled: bool = False) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
        if not isinstance(payload, dict):
            raise ValueError("Expected a result object")
        return payload if "error" in payload else _decode_result(payload, cancelled=cancelled)
    except (OSError, ValueError) as error:
        raise RuntimeError("Solver worker returned an invalid or missing result") from error


def _report_progress(record, on_log, on_progress):
    event = decode_progress(record)
    if on_progress is not None:
        on_progress(event)
    if isinstance(event, ModelStats):
        message = (
            f"Model: {event.label} — {event.variables:,} variables, "
            f"{event.constraints:,} constraints ({event.stage})"
        )
    elif isinstance(event, SearchStats):
        message = search_summary(event).replace("\n", " · ")
    else:
        message = "Phase: " + event
    on_log(message)


def _decode_result(payload: dict[str, Any], *, cancelled: bool = False) -> dict[str, Any]:
    try:
        result = CaseResult.from_dict(payload)
        if cancelled:
            result.raw["cancellation"] = {
                **result.raw.get("cancellation", {}),
                "requested": True,
                "incumbent_retained": result.income is not None,
            }
        return result.to_dict()
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("Solver worker returned an invalid result object") from error
