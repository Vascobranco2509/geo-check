"""Collect everything a check may look at, once, then hand it around.

The homepage is always fetched, because a homepage that does not answer 200
aborts the run and there is nothing to report without it. The sampled pages are
different: robots.txt is consulted for this tool's own user agent before any of
them is requested. A tool that reads robots.txt for a living does not get to
ignore one.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from protego import Protego

from .fetch import USER_AGENT, FetchResult, fetch, new_client
from .models import PageContext, SiteContext
from .robots import classify, looks_like_robots
from .sitemap import collect_urls, is_page, looks_like_sitemap, sample


class SiteUnavailable(Exception):
    """The run cannot produce an honest score, so it produces an error."""

    def __init__(self, domain: str, reason: str) -> None:
        super().__init__(reason)
        self.domain = domain
        self.reason = reason


def normalise_base(domain: str) -> str:
    """Turn whatever the user typed into a scheme and host, with no path."""
    raw = domain.strip()
    if not raw:
        raise SiteUnavailable(domain, "empty domain")
    if "//" not in raw:
        raw = "https://" + raw
    parts = urlsplit(raw)
    if not parts.netloc:
        raise SiteUnavailable(domain, f"could not read a host from {domain!r}")
    scheme = parts.scheme or "https"
    return f"{scheme}://{parts.netloc}"


def _origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _as_page(result: FetchResult) -> PageContext:
    return PageContext(
        url=result.final_url,
        status=result.status or 0,
        headers=result.headers,
        html=result.text,
    )


def build_site(domain: str, pages: int = 5, fetcher=None) -> SiteContext:
    """Fetch the homepage, robots.txt, the sitemap, llms.txt and a page sample.

    fetcher takes a URL and returns a FetchResult. It exists so the test suite
    can replay saved responses instead of touching the network, which is the
    only way a 500 site robustness run can live inside pytest.
    """
    base = normalise_base(domain)
    errors: list[str] = []
    client = new_client() if fetcher is None else None
    if fetcher is None:

        def fetcher(url: str) -> FetchResult:
            return fetch(url, client)

    try:
        home = fetcher(f"{base}/")
        if home.error and base.startswith("https://"):
            # Plenty of older sites, and a good slice of this corpus,
            # still answer only over http.
            plain = "http://" + base[len("https://") :]
            retry = fetcher(f"{plain}/")
            if retry.status is not None:
                errors.append(f"https failed ({home.error}), fell back to http")
                home, base = retry, plain

        if home.error:
            raise SiteUnavailable(domain, f"homepage unreachable: {home.error}")
        if home.status != 200:
            raise SiteUnavailable(domain, f"homepage returned HTTP {home.status}")

        # Redirects decide the real origin. example.pt may well be www.example.pt,
        # and robots.txt lives at the host that answered, not the one typed.
        base = _origin_of(home.final_url)

        robots = fetcher(f"{base}/robots.txt")
        robots_txt, robots_is_real = _read_robots(robots, errors)
        verdicts = classify(robots_txt, base)
        sitemap_url, declared_url = _find_sitemap(base, robots_txt, fetcher, errors)
        llms_txt = _read_llms_txt(base, fetcher)
        sampled = _sample_pages(base, sitemap_url, robots_txt, pages - 1, fetcher, errors)

        return SiteContext(
            domain=domain,
            base_url=base,
            robots_txt=robots_txt,
            robots_status=robots.status,
            robots_is_real=robots_is_real,
            robots_body=robots.text if robots.status == 200 else None,
            agent_verdicts=verdicts,
            sitemap_url=sitemap_url,
            sitemap_declared_url=declared_url,
            llms_txt=llms_txt,
            pages=[_as_page(home), *sampled],
            errors=errors,
        )
    finally:
        if client is not None:
            client.close()


def _read_robots(robots: FetchResult, errors: list[str]) -> tuple[str | None, bool]:
    """None means treat the site as having no robots.txt, which allows everything.

    A 4xx is a plain absence. A 5xx or a network failure is recorded, and also
    treated as absence, because inventing a block the site never declared would
    be worse than saying so in the notes.
    """
    if robots.error:
        errors.append(f"robots.txt could not be fetched: {robots.error}")
        return None, False
    if robots.status != 200:
        if robots.status is not None and robots.status >= 500:
            errors.append(f"robots.txt returned HTTP {robots.status}, treated as absent")
        return None, False
    if not looks_like_robots(robots.text, robots.content_type):
        errors.append("robots.txt returned 200 but the body is not robots syntax")
        return None, False
    return robots.text, True


def _read_llms_txt(base: str, fetcher) -> str | None:
    """The body decides, same as robots.txt. Many 404 handlers answer 200 with HTML."""
    result = fetcher(f"{base}/llms.txt")
    if not result.ok:
        return None
    head = result.text[:500].lstrip().lower()
    if head.startswith("<!doctype") or "<html" in head:
        return None
    return result.text


def _find_sitemap(
    base: str, robots_txt: str | None, fetcher, errors: list[str]
) -> tuple[str | None, str | None]:
    """Returns (the sitemap that answered, the one robots.txt declared)."""
    declared: list[str] = []
    if robots_txt:
        declared = [url for url in Protego.parse(robots_txt).sitemaps if url]

    declared_url = declared[0] if declared else None
    for candidate in [*declared, f"{base}/sitemap.xml"]:
        result = fetcher(candidate)
        if looks_like_sitemap(result):
            return result.final_url, declared_url

    if declared_url:
        errors.append(f"sitemap declared at {declared_url} did not answer with a sitemap")
    return None, declared_url


def _sample_pages(
    base: str,
    sitemap_url: str | None,
    robots_txt: str | None,
    count: int,
    fetcher,
    errors: list[str],
) -> list[PageContext]:
    """Pick and fetch the sample. The choice is settled before a request goes out."""
    if count <= 0:
        return []
    if not sitemap_url:
        errors.append("no sitemap found, so only the homepage was sampled")
        return []

    urls = collect_urls(sitemap_url, fetcher, errors)
    home = base.rstrip("/")
    candidates = [url for url in urls if is_page(url) and url.rstrip("/") != home]
    if not candidates:
        errors.append("the sitemap listed no pages beyond the homepage")
        return []

    parser = Protego.parse(robots_txt) if robots_txt else None
    if parser is None:
        permitted = candidates
    else:
        permitted = [url for url in candidates if parser.can_fetch(url, USER_AGENT)]
        skipped = len(candidates) - len(permitted)
        if skipped:
            errors.append(f"robots.txt disallows geo-check on {skipped} sampled URLs, skipped")
    if not permitted:
        errors.append("robots.txt disallows geo-check on every page in the sitemap")
        return []

    pages: list[PageContext] = []
    for url in sample(permitted, count):
        result = fetcher(url)
        if result.error:
            errors.append(f"page {url}: {result.error}")
            continue
        # A non 200 is kept on purpose. A sitemap listing dead URLs is a real
        # finding, and pages_reachable is the check that has to see it.
        pages.append(_as_page(result))
    return pages
