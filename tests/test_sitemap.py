"""Sitemap parsing and page sampling. Offline, hand written XML."""

from geo_check.fetch import FetchResult
from geo_check.sitemap import collect_urls, is_page, looks_like_sitemap, parse_sitemap, sample

URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.pt/artigo-um</loc><lastmod>2026-08-01</lastmod></url>
  <url><loc>https://example.pt/artigo-dois</loc></url>
  <url><loc>https://example.pt/manual.pdf</loc></url>
</urlset>"""

INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.pt/wp-sitemap-posts-post-1.xml</loc></sitemap>
  <sitemap><loc>https://example.pt/wp-sitemap-posts-post-2.xml</loc></sitemap>
</sitemapindex>"""

NO_NAMESPACE = """<urlset>
  <url><loc>https://example.pt/sem-namespace</loc></url>
</urlset>"""


def result(text, status=200, content_type="application/xml", url="https://example.pt/sitemap.xml"):
    return FetchResult(
        url=url,
        final_url=url,
        status=status,
        headers={"content-type": content_type},
        text=text,
    )


def test_a_urlset_yields_pages_and_no_nested_sitemaps():
    pages, nested = parse_sitemap(URLSET)
    assert pages == [
        "https://example.pt/artigo-um",
        "https://example.pt/artigo-dois",
        "https://example.pt/manual.pdf",
    ]
    assert nested == []


def test_an_index_yields_nested_sitemaps_and_no_pages():
    pages, nested = parse_sitemap(INDEX)
    assert pages == []
    assert nested == [
        "https://example.pt/wp-sitemap-posts-post-1.xml",
        "https://example.pt/wp-sitemap-posts-post-2.xml",
    ]


def test_a_sitemap_without_a_namespace_still_parses():
    pages, _ = parse_sitemap(NO_NAMESPACE)
    assert pages == ["https://example.pt/sem-namespace"]


def test_malformed_xml_returns_nothing_instead_of_raising():
    assert parse_sitemap("<urlset><url><loc>https://x.pt/a</loc>") == (["https://x.pt/a"], [])
    assert parse_sitemap("") == ([], [])
    assert parse_sitemap("not xml at all") == ([], [])


def test_external_entities_are_not_resolved():
    """A sitemap is an untrusted file from an arbitrary host."""
    hostile = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE urlset [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        "<urlset><url><loc>&xxe;</loc></url></urlset>"
    )
    pages, _ = parse_sitemap(hostile)
    assert pages == [] or all("root:" not in page for page in pages)


def test_sampling_is_stable_across_runs():
    urls = [f"https://example.pt/{i}" for i in range(50)]
    assert sample(urls, 5) == sample(urls, 5)
    assert len(sample(urls, 5)) == 5


def test_sampling_does_not_just_take_the_first_urls_in_order():
    urls = [f"https://example.pt/{i:03d}" for i in range(50)]
    assert sample(urls, 5) != sorted(urls)[:5]


def test_sampling_keeps_nested_sitemap_urls():
    """Filtering by extension here returned nothing for every sitemap index."""
    nested = [f"https://example.pt/wp-sitemap-posts-post-{i}.xml" for i in range(20)]
    assert len(sample(nested, 5)) == 5


def test_is_page_rejects_files_that_cannot_be_read():
    assert is_page("https://example.pt/artigo") is True
    assert is_page("https://example.pt/artigo?ref=x") is True
    assert is_page("https://example.pt/manual.pdf") is False
    assert is_page("https://example.pt/foto.JPG") is False
    assert is_page("https://example.pt/wp-sitemap.xml") is False


def test_looks_like_sitemap_rejects_html_and_accepts_xml():
    assert looks_like_sitemap(result(URLSET)) is True
    assert looks_like_sitemap(result("<!DOCTYPE html><html><body>404", "text/html")) is False
    assert looks_like_sitemap(result(URLSET, status=404)) is False


def test_a_compressed_sitemap_counts_as_reachable_without_being_parsed():
    compressed = result("binary junk", url="https://example.pt/sitemap.xml.gz")
    assert looks_like_sitemap(compressed) is True


def test_collect_urls_follows_one_index_level():
    """The fetcher is injected, which is also how the offline suite runs."""
    fetched: list[str] = []

    def fake_fetcher(url):
        fetched.append(url)
        return result(INDEX if url.endswith("sitemap.xml") else URLSET, url=url)

    errors: list[str] = []
    urls = collect_urls("https://example.pt/sitemap.xml", fake_fetcher, errors)

    assert len(fetched) == 3
    assert urls.count("https://example.pt/artigo-um") == 2
    assert errors == []


def test_collect_urls_logs_a_nested_sitemap_that_does_not_parse():
    def fake_fetcher(url):
        if url.endswith("sitemap.xml"):
            return result(INDEX, url=url)
        return result("<!DOCTYPE html><html>oops", content_type="text/html", url=url)

    errors: list[str] = []
    assert collect_urls("https://example.pt/sitemap.xml", fake_fetcher, errors) == []
    assert len(errors) == 2
    assert all("did not parse" in error for error in errors)
