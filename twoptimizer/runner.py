"""Asynchronous subprocess lifetime, including cancellation and terminal exit."""

import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory


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

    async def run(self, config, on_log):
        with TemporaryDirectory(prefix="twoptimizer-") as directory:
            request_path, result_path = (
                Path(directory) / "request.json",
                Path(directory) / "result.json",
            )
            request_path.write_text(json.dumps(asdict(config)))
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
                async for line in process.stdout:
                    on_log(line.decode(errors="replace").rstrip()[:1000])
                await process.wait()
                if self.cancelled:
                    return None
                if not result_path.exists():
                    raise RuntimeError(
                        f"Solver worker exited with code {process.returncode}; see the log."
                    )
                result = json.loads(result_path.read_text())
                if "error" in result:
                    raise RuntimeError(result["error"])
                if process.returncode:
                    raise RuntimeError(f"Solver worker exited with code {process.returncode}.")
                return result
            finally:
                if process.returncode is None:
                    await self.stop()
