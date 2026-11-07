"""Bounded HTTPS retrieval, response hashes, and replayable source caches."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from time import sleep
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class Sources:
    def __init__(self, cache, offline=False, workers=3):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self.workers = workers
        self.records = {}

    def get(self, url):
        if not url.startswith(
            (
                "https://www.honga.net/totalwar/",
                "https://liquidwork.github.io/shogun2-encyclopedia/",
                "https://shogun2-encyclopedia.com/",
                "https://steamcommunity.com/sharedfiles/",
                "https://r2encv2.totalwar.com/",
                "https://r2enc.totalwar.com/",
            )
        ):
            raise ValueError("Unrecognized reference source")
        path = self.cache / (sha256(url.encode()).hexdigest() + ".html")
        if not path.exists():
            if self.offline:
                raise FileNotFoundError(f"Missing offline source: {url}")
            request = Request(
                url, headers={"User-Agent": "twoptimizer-data-import/1.0"}
            )
            for attempt in range(3):
                try:
                    with urlopen(request, timeout=45) as response:
                        raw = response.read(12 * 1024 * 1024 + 1)
                    break
                except HTTPError as error:
                    if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                        raise RuntimeError(
                            f"Source request failed: {url} (HTTP {error.code})"
                        ) from error
                    retry = error.headers.get("Retry-After", "")
                    if retry.isdigit() and int(retry) > 30:
                        raise RuntimeError(
                            f"Source requests a longer pause; retry the import later: {url}"
                        ) from error
                    sleep(max(2**attempt, int(retry) if retry.isdigit() else 0))
            if len(raw) > 12 * 1024 * 1024:
                raise ValueError("Reference response exceeds size limit")
            path.write_bytes(raw)
        raw = path.read_bytes()
        self.records[url] = {
            "url": url,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        return raw.decode("utf-8-sig")

    def many(self, urls):
        urls = list(dict.fromkeys(urls))
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            return dict(zip(urls, pool.map(self.get, urls)))
