"""Sitemap reading and deterministic page sampling.

Two runs against an unchanged site must pick the same pages, otherwise a score
moves for reasons nobody can explain. Sorting the URLs and taking the first N
would be deterministic but would also always land on /404, /about and whatever
else sorts early. Sorting by the hash of the URL is just as stable and spreads
the sample across the site.

XML from a stranger is parsed with entity resolution and network access off.
A sitemap is an untrusted file fetched from an arbitrary host.
"""

from __future__ import annotations

import hashlib
import re

from lxml import etree

from .fetch import FetchResult

# A news site can list a hundred monthly sitemaps. Following all of them would
# cost a hundred requests for five sampled pages.
MAX_NESTED_FETCHES = 5
MAX_URLS = 5000
NON_PAGE_SUFFIXES = (
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".mp4",
    ".mp3",
    ".zip",
    ".xml",
    ".json",
    ".css",
    ".js",
)

_XML_DECLARATION = re.compile(r"^\s*<\?xml[^>]*\?>")
_PARSER = etree.XMLParser(recover=True, resolve_entities=False, no_network=True)


def looks_like_sitemap(result: FetchResult) -> bool:
    """Reachable and plausibly a sitemap, not a soft 404 dressed as HTML."""
    if not result.ok:
        return False
    content_type = result.content_type.lower()
    if result.final_url.endswith(".gz") or "gzip" in content_type:
        # A compressed sitemap is not decoded. It counts as declared and
        # reachable, and contributes no URLs to the sample.
        return True
    head = result.text[:600].lstrip().lower()
    if "html" in content_type or head.startswith("<!doctype html") or "<html" in head:
        return False
    return head.startswith("<?xml") or "<urlset" in head or "<sitemapindex" in head


def parse_sitemap(xml: str) -> tuple[list[str], list[str]]:
    """Split a sitemap into (page URLs, nested sitemap URLs).

    Namespaces are ignored on purpose. Plenty of real sitemaps declare none, or
    declare the wrong one, and the local tag name is unambiguous either way.
    """
    body = _XML_DECLARATION.sub("", xml).strip().encode("utf-8")
    if not body:
        return [], []
    root = etree.fromstring(body, parser=_PARSER)
    if root is None:
        return [], []

    pages: list[str] = []
    nested: list[str] = []
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        if etree.QName(element).localname != "loc":
            continue
        url = (element.text or "").strip()
        if not url:
            continue
        parent = element.getparent()
        parent_name = etree.QName(parent).localname if parent is not None else ""
        if parent_name == "sitemap":
            nested.append(url)
        else:
            pages.append(url)
    return pages, nested


def is_page(url: str) -> bool:
    """Sitemaps list PDFs and images too, and none of those can be read."""
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    return not path.endswith(NON_PAGE_SUFFIXES)


def sample(urls: list[str], count: int) -> list[str]:
    """A stable pick, so two runs over an unchanged sitemap choose the same items.

    Deliberately free of any notion of what a page is. This picks nested
    sitemaps as well, and those all end in .xml, so filtering here would
    silently return nothing for every sitemap index in existence.
    """
    ordered = sorted(set(urls), key=lambda url: hashlib.sha256(url.encode("utf-8")).digest())
    return ordered[:count]


def collect_urls(sitemap_url: str, fetcher, errors: list[str]) -> list[str]:
    """Every page URL reachable from this sitemap, following one index level.

    The nested sitemaps that get followed are themselves chosen by hash, not by
    file order, so a site that names its sitemaps by month is not sampled
    entirely from January.
    """
    result = fetcher(sitemap_url)
    if not looks_like_sitemap(result):
        errors.append(f"sitemap at {sitemap_url} did not parse as a sitemap")
        return []

    pages, nested = parse_sitemap(result.text)
    if nested:
        followed = (
            sample(nested, MAX_NESTED_FETCHES) if len(nested) > MAX_NESTED_FETCHES else nested
        )
        if len(nested) > MAX_NESTED_FETCHES:
            errors.append(
                f"sitemap index lists {len(nested)} sitemaps, sampled {MAX_NESTED_FETCHES} of them"
            )
        for child in followed:
            child_result = fetcher(child)
            if not looks_like_sitemap(child_result):
                errors.append(f"nested sitemap at {child} did not parse as a sitemap")
                continue
            child_pages, _ = parse_sitemap(child_result.text)
            pages.extend(child_pages)
            if len(pages) >= MAX_URLS:
                break

    return pages[:MAX_URLS]
