"""Recorded HTTP responses, so the test suite never touches the network.

One gzipped JSON file per domain. Refreshing them is a deliberate act, run from
scripts/refresh_fixtures.py; the tests only ever replay.

A fetch for a URL the fixture does not hold returns a failure with that reason
rather than inventing a response. A replay that quietly answers 404 for anything
it has not seen would let a broken sampler pass.
"""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

from .fetch import FetchResult

FORMAT_VERSION = 1
SUFFIX = ".json.gz"


def path_for(directory: Path, domain: str) -> Path:
    return Path(directory) / (domain.replace("/", "_") + SUFFIX)


class Recorder:
    """Wraps a fetcher and keeps every response it returns."""

    def __init__(self, fetcher) -> None:
        self._fetcher = fetcher
        self.responses: dict[str, dict] = {}

    def __call__(self, url: str) -> FetchResult:
        result = self._fetcher(url)
        self.responses[url] = {
            "final_url": result.final_url,
            "status": result.status,
            "headers": result.headers,
            "text": result.text,
            "error": result.error,
            "truncated": result.truncated,
        }
        return result


class Replayer:
    """A fetcher backed by a recorded file."""

    def __init__(self, responses: dict[str, dict]) -> None:
        self.responses = responses
        self.missed: list[str] = []

    def __call__(self, url: str) -> FetchResult:
        recorded = self.responses.get(url)
        if recorded is None:
            self.missed.append(url)
            return FetchResult(
                url=url,
                final_url=url,
                status=None,
                error="not in fixture",
            )
        return FetchResult(
            url=url,
            final_url=recorded["final_url"],
            status=recorded["status"],
            headers=recorded.get("headers", {}),
            text=recorded.get("text", ""),
            error=recorded.get("error"),
            truncated=recorded.get("truncated", False),
        )


def save(directory: Path, domain: str, responses: dict[str, dict], outcome: str) -> Path:
    """Write one domain's responses, stamped so stale fixtures are visible."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "format_version": FORMAT_VERSION,
        "domain": domain,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "outcome": outcome,
        "responses": responses,
    }
    target = path_for(directory, domain)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    with gzip.open(target, "wb", compresslevel=9) as handle:
        handle.write(body)
    return target


def load(directory: Path, domain: str) -> dict:
    with gzip.open(path_for(directory, domain), "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def available(directory: Path) -> list[str]:
    """Every domain with a fixture on disk, in a stable order."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted(p.name[: -len(SUFFIX)] for p in directory.glob("*" + SUFFIX))
