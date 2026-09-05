"""HTTP layer.

Rules, from the scaffold and kept:
  - Identify honestly in the user agent, with a link to the repository. This
    tool reads robots.txt for a living, it does not get to pretend to be a
    browser.
  - Never raise on a network problem. Return a typed failure with a reason, so
    the 906 site robustness run can log it instead of crashing.
  - Timeouts on every request. One slow site must not hang the run.
  - Follow redirects, but record the final URL.

The body is read in chunks against a byte ceiling. A timeout bounds how long a
single read may block, not how much a site may send, and a slow drip of a very
large response would otherwise stall a sweep across hundreds of unknown hosts.
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field

import httpx

USER_AGENT = "geo-check/0.1 (+https://github.com/vasco-branco06/geo-check)"
TIMEOUT_SECONDS = 15.0
MAX_RETRIES = 2
MAX_BYTES = 5_000_000
RETRY_BACKOFF_SECONDS = 0.5

# Transient on the server side. A 4xx is an answer, not a failure, so it is
# returned as is and never retried.
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
# A 429 is not a blip, it is a bot manager asking to be left alone. Half a second
# is an insult. This was found by hitting forty Shopify storefronts behind
# Cloudflare in a burst and having every one of them answer 429 for the next
# several minutes, including one that had answered 200 an hour earlier.
BACKOFF_ON_429_SECONDS = 20.0
MAX_HONOURED_RETRY_AFTER = 120.0


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int | None
    headers: dict[str, str] = field(default_factory=dict)
    text: str = ""
    error: str | None = None
    # True when the response hit MAX_BYTES and the tail was discarded.
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None and self.status == 200

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "")


def new_client() -> httpx.Client:
    """A client the caller can reuse across the handful of requests per site."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"},
        timeout=httpx.Timeout(TIMEOUT_SECONDS),
        follow_redirects=True,
        max_redirects=10,
    )


def _read_capped(response: httpx.Response) -> tuple[str, bool]:
    """Read the body up to MAX_BYTES and decode it."""
    chunks: list[bytes] = []
    size = 0
    truncated = False
    for chunk in response.iter_bytes():
        chunks.append(chunk)
        size += len(chunk)
        if size >= MAX_BYTES:
            truncated = True
            break
    # charset_encoding is the declared charset. Guessing beyond that is a
    # rabbit hole, and replacing undecodable bytes never loses a directive or a
    # tag, which is all the checks read.
    encoding = response.charset_encoding or "utf-8"
    try:
        text = b"".join(chunks).decode(encoding, errors="replace")
    except LookupError:
        text = b"".join(chunks).decode("utf-8", errors="replace")
    return text, truncated


def fetch(url: str, client: httpx.Client | None = None) -> FetchResult:
    """GET a URL. Always returns a result, never raises."""
    owns_client = client is None
    client = client or new_client()
    last_failure: FetchResult | None = None

    try:
        for attempt in range(MAX_RETRIES + 1):
            try:
                with client.stream("GET", url) as response:
                    text, truncated = _read_capped(response)
                    result = FetchResult(
                        url=url,
                        final_url=str(response.url),
                        status=response.status_code,
                        headers={k.lower(): v for k, v in response.headers.items()},
                        text=text,
                        truncated=truncated,
                    )
                if response.status_code in RETRY_STATUSES and attempt < MAX_RETRIES:
                    last_failure = result
                    time.sleep(_pause_for(result, attempt))
                    continue
                return result
            except httpx.TooManyRedirects:
                return _failure(url, "too_many_redirects")
            except httpx.UnsupportedProtocol:
                return _failure(url, "unsupported_protocol")
            except httpx.InvalidURL:
                # InvalidURL inherits from Exception and not from HTTPError, so
                # it walks past every clause below and out of the process. A
                # domain with a colon in it is enough to produce one.
                return _failure(url, "invalid_url")
            except httpx.TimeoutException:
                last_failure = _failure(url, "timeout")
            except httpx.TransportError as exc:
                failure = _failure(url, f"network: {type(exc).__name__}")
                if _name_does_not_resolve(exc):
                    return failure
                last_failure = failure
            except httpx.HTTPError as exc:
                return _failure(url, f"http: {type(exc).__name__}")

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))

        return last_failure or _failure(url, "unknown")
    finally:
        if owns_client:
            client.close()


def _pause_for(result: FetchResult, attempt: int) -> float:
    """How long to wait before retrying, honouring Retry-After when it is sane."""
    header = result.headers.get("retry-after", "").strip()
    if header.isdigit():
        return min(float(header), MAX_HONOURED_RETRY_AFTER)
    if result.status == 429:
        return BACKOFF_ON_429_SECONDS * (attempt + 1)
    return RETRY_BACKOFF_SECONDS * (attempt + 1)


def _failure(url: str, reason: str) -> FetchResult:
    return FetchResult(url=url, final_url=url, status=None, error=reason)


def _name_does_not_resolve(exc: BaseException) -> bool:
    """Whether DNS said the name does not exist.

    A TransportError is normally worth another go, which is why one is not
    returned immediately. A name that does not resolve is the exception: no
    amount of waiting invents a DNS record, and retrying it three times over
    https and three more over http spent thirty-six seconds proving that a
    typo was still a typo. httpx wraps the original, so the chain is what
    carries the answer.
    """
    cause: BaseException | None = exc
    while cause is not None:
        if isinstance(cause, socket.gaierror):
            return True
        cause = cause.__cause__
    return False
