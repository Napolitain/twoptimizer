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
from twoptimizer.progress import PREFIX


class CaseRunner:
    def __init__(self):
        self.process = None
        self.cancelled = False

    async def stop(self):
        self.cancelled = True
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

    async def _read_output(self, process, on_log, on_progress, started):
        startup_seconds = None
        if process.stdout is None:
            raise RuntimeError("Solver worker output pipe is unavailable")
        async for line in process.stdout:
            text = line.decode(errors="replace").rstrip()
            if text.startswith(PREFIX):
                if startup_seconds is None:
                    startup_seconds = perf_counter() - started
                phase = json.loads(text[len(PREFIX) :])["phase"]
                if on_progress is not None:
                    on_progress(phase)
                on_log("Phase: " + phase)
            else:
                on_log(text[:1000])
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


def _decode_result(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return CaseResult.from_dict(payload).to_dict()
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError("Solver worker returned an invalid result object") from error
