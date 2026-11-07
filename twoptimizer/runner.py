"""Asynchronous subprocess lifetime, including cancellation and terminal exit."""

import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from twoptimizer.progress import PREFIX


class CaseRunner:
    def __init__(self):
        self.process = None
        self.cancelled = False

    async def stop(self):
        self.cancelled = True
        process = self.process
        if process is not None and process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                return
            try:
                await asyncio.wait_for(process.wait(), 2)
            except TimeoutError:
                process.kill()
                await process.wait()

    async def run(self, config, on_log, on_progress=None):
        started = perf_counter()
        startup_seconds = None
        with TemporaryDirectory(prefix="twoptimizer-") as directory:
            request_path, result_path = (
                Path(directory) / "request.json",
                Path(directory) / "result.json",
            )
            request_path.write_text(json.dumps(asdict(config)))
            self.process = await asyncio.create_subprocess_exec(
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
                if self.cancelled:
                    await self.stop()
                async for line in self.process.stdout:
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
                await self.process.wait()
                if self.cancelled:
                    return None
                if not result_path.exists():
                    raise RuntimeError(
                        f"Solver worker exited with code {self.process.returncode}; see the log."
                    )
                result = json.loads(result_path.read_text())
                if "error" in result:
                    raise RuntimeError(result["error"])
                if self.process.returncode:
                    raise RuntimeError(
                        f"Solver worker exited with code {self.process.returncode}."
                    )
                result.setdefault("timings", {}).update(
                    worker_wall_seconds=perf_counter() - started
                )
                if startup_seconds is not None:
                    result["timings"]["worker_startup_seconds"] = startup_seconds
                return result
            finally:
                if self.process.returncode is None:
                    await self.stop()
