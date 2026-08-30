# Changelog

Notable changes, newest first. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added

- Validation across 500 real sites, with the evidence in `docs/VALIDATION.md`
- An accuracy harness, `scripts/verify_accuracy.py`, reading every `robots.txt`
  three ways and comparing per agent
- Continuous integration across Python 3.10 to 3.14, plus a clean install of the
  built wheel
- `data/corpus_manifest.csv`, the SHA-256 of every `robots.txt` in the corpus as
  it was read, with `scripts/build_manifest.py` to rebuild it and
  `scripts/verify_manifest.py` to check rows against the live web. The 208 MB of
  recordings do not ship, so the fingerprints do
- A sectioning measure inside `answer_shaped_content`, with thresholds taken from
  12301 blocks across 868 pages rather than borrowed
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and issue templates

### Fixed

Three defects in `robots.txt` handling, all found by the validation harness
before anyone hit them in the field. Each has a regression test.

- **User agents were matched by substring.** The underlying library matches the
  way a full `User-Agent` header requires; this tool passes a bare product token.
  A site writing `User-agent: bot` would have silently blocked GPTBot, Googlebot,
  Bingbot, PerplexityBot, OAI-SearchBot and Claude-SearchBot at once. Group
  selection moved into `robots.py`; the library still decides every path
  question.
- **Groups declaring the same agent were not merged.** RFC 9309 section 2.2.1
  requires it, and a site that contradicts itself was getting whichever rule came
  first.
- **A bare `Crawl-delay` did not close a run of user-agent lines.** Two adjacent
  groups were being glued into one, so an agent inherited a rule aimed at
  another.

Also fixed: a platform detector that labelled an email marketing SaaS as a shop
because its marketing pages named every platform it integrates with. It now reads
the `generator` meta tag first.

### Changed

- Renamed from `geo-audit` to `geo-check`. The former was taken on PyPI by a
  similar tool, and PyPI normalises names.
- The fetcher backs off twenty seconds on HTTP 429 and honours `Retry-After`, and
  the fixture recorder runs four domains at a time with staggered starts. Eight
  in parallel was enough to have a CDN challenge a whole batch for half an hour,
  which would have published ten reachable sites as unreachable.
- `robots.txt` is honoured for this tool's own user agent when sampling pages.
- The body of `/robots.txt` decides whether it is real, with the `Content-Type`
  header only corroborating. A site serving a valid `robots.txt` as `text/html`
  was being read as having none at all.
