# Changelog

Notable changes, newest first. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

## v0.1.0 - 2026-08-30

First release. The GitHub Action is published to the
[Marketplace](https://github.com/marketplace/actions/geo-check) from this tag,
under `Vascobranco2509/geo-check@v0`.

### Added

- `action.yml`, a GitHub Action. Five lines in any workflow audits a site on
  every deploy and fails the build below a score you set. It installs the exact
  ref the caller pinned, so the audit and the rubric that scored it never drift
  apart, and it writes the full report into the run summary
- A manual `audit a site` workflow, so anyone can run the tool from the Actions
  tab of a fork without installing anything. Manual only: the suite is offline by
  design and CI stays that way
- `docs/CRAWLERS.md`, all 25 user agents with vendor, bucket, whether the vendor
  documents it as honouring `robots.txt`, and a link to that documentation.
  Generated from `agents.json`, which stays the source of truth
- `assets/output.png` and `assets/social-preview.png`, both rendered from a real
  recorded run rather than mocked up
- Validation across 500 real sites, with the evidence in `docs/VALIDATION.md`
- An accuracy harness, `scripts/verify_accuracy.py`, reading every `robots.txt`
  three ways and comparing per agent
- Continuous integration across Python 3.10 to 3.14, plus a clean install of the
  built wheel
- `data/corpus_manifest.csv`, the SHA-256 of every `robots.txt` in the corpus as
  it was read, with `scripts/build_manifest.py` to rebuild it and
  `scripts/verify_manifest.py` to check rows against the live web. The 208 MB of
  recordings do not ship, so the fingerprints do
- `data/corpus_categories.csv`, site type for all 500 domains, read by
  `scripts/run_study.py`. Hand assigned and checked against recorded pages;
  `CONTRIBUTING.md` states the method, the boundaries, and what reading every row
  back against its recorded homepage found
- A sectioning measure inside `answer_shaped_content`, with thresholds taken from
  12301 blocks across 868 pages rather than borrowed
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and issue templates

### Changed

- The README leads with the result. The real output sits above the fold as a
  rendered terminal, the crawler table moved to `docs/CRAWLERS.md`, and a section
  answering the questions people actually ask replaces detail that belonged in
  `docs/`. Every link is absolute, because relative links break on the PyPI page
- `data/corpus_500.txt` is one flat block ordered by sha256 of the domain, with
  no section comments. Site type moved to its own file

### Fixed

Ten figures in the documentation were corrected against the data behind them,
including `excalidraw.com`'s Readability score, the share of pages that are a
single block, the distance between the contradictory `CCBot` rules, and the
scope of the hand-traced block verdicts. Two claims were removed for resting on
data that does not ship, and the JavaScript heuristic's known false negative is
now stated in `docs/RUBRIC.md` rather than counted out of the sample.

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
