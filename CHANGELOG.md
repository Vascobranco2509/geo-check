# Changelog

Notable changes, newest first. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## v0.3.0 - 2026-09-05

### Added

- Five citation crawlers the list did not know about, each with its vendor's own
  documentation: `Meta-WebIndexer`, `MistralAI-Index`, `Amzn-SearchBot`,
  `DuckAssistBot` and `YouBot`. Meta and Mistral had no citation crawler here at
  all, so a site shut out of Meta AI or Mistral search scored clean. Meta's page
  says allowing theirs helps Meta AI cite and link your content; Mistral
  documents theirs as indexing for search and explicitly not for training
- Three on demand fetchers documented as not honouring robots.txt: `Amzn-User`,
  `Google-GeminiNotebook` and `Google-Agent`. Google was represented here as
  honouring robots.txt everywhere, and its own page says its user triggered
  fetchers generally ignore it
- `scripts/build_crawlers_doc.py`. `docs/CRAWLERS.md` has claimed since the first
  release that it is generated from `agents.json`, and nothing generated it, so
  it fell behind. `tests/test_crawlers_doc.py` now fails when the two disagree,
  and it also binds the count the README quotes

### Removed

- `cohere-ai`. Cohere now publishes a crawler page whose bot table reads N/A and
  which states that it does not use bots or user agents to crawl the web for
  training. The token appears nowhere on it

### Changed

- The citation bucket holds eleven agents rather than six, so the 50 points split
  eleven ways. A site blocking one of the original six is penalised less than it
  was, which is right, because it is still reachable by ten others. A site
  blocking with a wildcard is penalised more, which is also right: `casa.pt` goes
  from 48.7 to 44.1 because it shuts out nine citation crawlers and the old list
  only knew about four of them
- `ai_only` now marks the AI answer crawlers established enough that blocking
  every one of them is a decision, rather than every crawler that only serves AI.
  This was measured before it was chosen. Flagging all five newcomers took the
  blackout detection, which `docs/RUBRIC.md` calls the failure this tool exists to
  find, from 18 sites in the corpus to 4, because nobody blocks a crawler they
  have never heard of. Narrowing the flag holds it at 18
- Entries whose documentation did not support them. `Bytespider` pointed at a
  webmaster portal that is not reachable and is not crawler documentation, so it
  now carries no link and says so; a new test refuses to let an undocumented
  entry sit in a bucket that scores. `Diffbot` reads disputed rather than yes,
  because the vendor says robots.txt is honoured by default and can be overridden
  by agreement. `ChatGPT-User` reads disputed rather than no, because OpenAI
  writes that the rules may not apply, which is weaker than Perplexity's flat
  statement that it ignores them

### Fixed

- `scripts/refresh_fixtures.py` no longer dies on the path written to keep it
  alive. The handler built its message by adding an exception to a string, which
  raises `TypeError` inside the `except`, so one unexpected crash took down a
  whole sweep instead of being logged as one domain's outcome
- Tests no longer hard code how many agents a bucket holds. Adding a crawler
  broke fifteen assertions that had no opinion about crawlers; they now read the
  size from the list and mean all of them, or none of them

## v0.2.0 - 2026-09-05

### Added

- Content signals. Sites that declare what AI systems may do with their content,
  through a `Content-Signal` line in robots.txt, now have that declaration read
  and translated into a sentence. Reported and never scored, like training
  posture. The recognised keys were taken from the 47 sites in the corpus that
  send the directive rather than from the draft specification, which describes
  two keys no site sends and omits two that most do. A further 8 sites publish
  the explanatory terms without declaring anything, which by those terms grants
  and restricts nothing, and is reported as its own state
- `SiteContext.robots_body`, the response body exactly as served. A robots.txt of
  nothing but comments is treated as absent for crawl rules, correctly, and can
  still carry a declaration worth reading

### Fixed

- The user fetch score no longer counts blocks that do not work. Three of the
  five agents in that bucket are documented by their own vendors as ignoring
  robots.txt, so a Disallow aimed at one of them changes nothing and now costs
  nothing. docs/RUBRIC.md had described this as a known weakness since the
  first release. Replaying the corpus measured it before the change: of 744
  scored sites, 61 block at least one of these agents, 53 score differently
  under the new rule, and 26 of those change letter grade. The reported counts
  are unchanged, because they report the robots.txt and not the score
- A domain containing a colon no longer ends the process with a traceback.
  `httpx.InvalidURL` inherits from `Exception` rather than from `HTTPError`, so
  it walked past every clause meant to catch it. It is now reported as
  `invalid_url`, like any other unreachable homepage
- A name that does not resolve is answered in about three seconds instead of
  thirty-six. A transport error is normally worth another go, so it was retried
  three times over https and three more over http. DNS saying the name does not
  exist is the one transport error that repetition cannot change
- `--json` and `--output` create the directory they are pointed at. The audit is
  finished by the time either is written, so a path into a directory that did
  not exist printed the whole report and then threw it away
- `--pages 0` and negative counts are refused. They were accepted, and quietly
  produced a run over one page

### Changed

- The skill installs with `pip install geo-check`. It previously said
  `pip install -e .`, which needs a checkout and a working directory that
  whoever installed the skill does not have
- The source distribution is 204 KB rather than 8.8 MB. The golden fixtures
  prove the tool against recorded sites, and nobody installing it needs them
- `py.typed` ships, so the `Typing :: Typed` classifier the package has declared
  from the start is now true and the annotations reach type checkers

### Security

- `SKILL.md` states that quoted robots.txt lines are data and not instructions.
  The report copies matched rules verbatim from a stranger's server, and at
  least one site in the validation corpus uses its robots.txt to address
  whichever agent is reading it. This has been in `SECURITY.md` since the first
  release and is now also where an assistant will read it

## v0.1.0 - 2026-08-30

First release. The GitHub Action is published to the
[Marketplace](https://github.com/marketplace/actions/geo-check) from this tag,
under `vasco-branco06/geo-check@v0`.

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
- Validation across 906 real sites, with the evidence in `docs/VALIDATION.md`
- An accuracy harness, `scripts/verify_accuracy.py`, reading every `robots.txt`
  three ways and comparing per agent
- Continuous integration across Python 3.10 to 3.14, plus a clean install of the
  built wheel
- `data/corpus_manifest.csv`, the SHA-256 of every `robots.txt` in the corpus as
  it was read, with `scripts/build_manifest.py` to rebuild it and
  `scripts/verify_manifest.py` to check rows against the live web. The 342 MB of
  recordings do not ship, so the fingerprints do
- `data/corpus_categories.csv`, site type for all 906 domains, read by
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
- `data/corpus.txt` is one flat block ordered by sha256 of the domain, with
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
