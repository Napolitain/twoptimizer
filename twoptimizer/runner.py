"""Asynchronous subprocess lifetime, including cancellation and terminal exit."""

import asyncio
import json
import os
import sys
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

from twoptimizer.errors import deserialize_error
from twoptimizer.models import CaseResult, RunConfig
from twoptimizer.progress import PREFIX, ModelStats, decode_progress


class CaseRunner:
    def __init__(self):
        self.process = None
        self.cancelled = False

    async def stop(self):
        self.cancelled = True
        await self._reap_process()

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
        if case_id is not None and not self.cancelled:
            raise RuntimeError("Solver worker exited before completing the case; see the log.")
        return startup_seconds

    async def run(self, config: RunConfig, on_log, on_progress=None):
        started = perf_counter()
        startup_seconds = None
        with TemporaryDirectory(prefix="twoptimizer-") as directory:
            request_path, result_path = (
                Path(directory) / "request.json",
                Path(directory) / "result.json",
            )
            request_path.write_text(json.dumps(config.to_dict()))
            process = self.process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "twoptimizer.worker",
                str(request_path),
                str(result_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            try:
                if process.stdout is None:
                    raise RuntimeError("Solver worker output pipe is unavailable")
                if self.cancelled:
                    await self.stop()
                startup_seconds = await self._read_output(process, on_log, on_progress, started)
                await process.wait()
                if self.cancelled:
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
                result = _decode_result(result)
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
        with TemporaryDirectory(prefix="twoptimizer-") as directory:
            request_path, result_path = (
                Path(directory) / "request.json",
                Path(directory) / "result.json",
            )
            request_path.write_text(json.dumps(config.to_dict()))
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
                }
                process.stdin.write((json.dumps(request) + "\n").encode())
                await process.stdin.drain()
                startup = await self._read_output(
                    process, on_log, on_progress, started, self._case_id
                )
                if self.cancelled:
                    return None
                payload = _read_batch_result(result_path)
                return payload, startup
            except BaseException as error:
                await self._close_process()
                if self.cancelled and isinstance(error, Exception):
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
            if completed is None:
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


def _read_batch_result(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
        if not isinstance(payload, dict):
            raise ValueError("Expected a result object")
        return payload if "error" in payload else _decode_result(payload)
    except (OSError, ValueError) as error:
        raise RuntimeError("Solver worker returned an invalid or missing result") from error


def _report_progress(record, on_log, on_progress):
    event = decode_progress(record)
    if on_progress is not None:
        on_progress(event)
    on_log(
        f"Model: {event.label} — {event.variables:,} variables, "
        f"{event.constraints:,} constraints ({event.stage})"
        if isinstance(event, ModelStats)
        else "Phase: " + event
    )


def _decode_result(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return CaseResult.from_dict(payload).to_dict()
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("Solver worker returned an invalid result object") from error
