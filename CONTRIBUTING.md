# Contributing

## The contribution worth the most

A correction to `src/geo_check/data/agents.json`.

That file decides which bucket every crawler sits in, and the buckets are what
the Access score rests on. Vendors rename crawlers, split them, and change what
they say about `robots.txt`, usually without announcing it. An entry that is
quietly wrong makes every score wrong in the same direction and nobody notices.

Entries need the vendor's own documentation URL. Not a crawler directory, not a
blog post. The file records what vendors say rather than what the field believes,
and the difference between those two is most of the reason this project exists.

There is an [issue template](.github/ISSUE_TEMPLATE/crawler-list.md) for it.

## Adding a check

One file in `src/geo_check/checks/`, one line in `REGISTRY` in
`src/geo_check/checks/__init__.py`. That is the whole extension mechanism, and
there will not be a plugin system in v1.

A check takes a `SiteContext` and returns a `CheckResult` carrying a ratio, a
severity, the evidence a human can verify, and a `Fix` where one applies. The
contract is in `src/geo_check/models.py`.

Two rules the existing checks follow and yours should:

**Evidence, not verdicts.** A check that says "heading structure is bad" is
useless. One that says "3 of 5 pages have no h1, and two skip from h1 to h4" can
be checked and acted on.

**Say when you are guessing.** Several checks are heuristics, and each one puts
`"heuristic": True` in its details and says so in its evidence line. A rubric
that hides which parts are inference is worse than one with fewer checks.

Changing a weight is a different matter. The rubric is fixed in `CLAUDE.md` and
the reasoning is in [docs/RUBRIC.md](docs/RUBRIC.md). Open an issue first.

## Running the suite

```bash
pip install -e ".[dev]"
```

```bash
pytest
```

About fifteen seconds, offline, no network. It includes the golden set of thirty hard
sites replayed from committed fixtures, and those require 100 percent: if one
fails, read the `robots.txt` in the fixture before touching the expectation. The
point of that file is that it is harder to change than the code.

```bash
ruff check src tests scripts && ruff format src tests scripts
```

CI runs both on every pull request, across Python 3.10 to 3.14, and also builds
the wheel and installs it into an empty environment.

## Fixtures

The 906 site corpus is recorded locally and not committed, because it is 342 MB
and truncating it was measured and rejected.

```bash
python scripts/refresh_fixtures.py --out tests/fixtures/corpus
```

That touches the live web and takes about forty minutes. Be polite: it defaults
to four domains at a time with staggered starts, and it defaults that way because
eight was enough to have a CDN answer 429 to a whole batch for half an hour. A
sweep is a request pattern and the pattern gets measured along with the sites.

After recording, rebuild the fingerprint manifest, which does ship:

```bash
python scripts/build_manifest.py
```

It writes `data/corpus_manifest.csv`, one row per domain with the read timestamp,
the outcome and the SHA-256 of the `robots.txt` body.

## Site type

`data/corpus_categories.csv` maps each of the 906 domains to one of ten types:
ecommerce, storefront, news, saas, blog, platform, reference, education,
government. `scripts/run_study.py` reads it, and adding a domain to the corpus
means adding a row here too, or the script fails loudly.

It lives apart from `data/corpus.txt` because that file is one flat block
with no sections. A section boundary orders the domains, and an ordering states
something about the corpus that a list of domains has no business stating.

**These are judgements, not measurements, and the file says so here because it
cannot say so in a CSV.** Each domain was assigned by hand from what the site is,
then checked against the title and meta description in its recorded homepage.
193 domains could be checked that way. The rest had aborted or returned a
challenge page, so there was nothing recorded to check against. Three of the 193
were wrong and were corrected: `owala.com` is a
WordPress blog rather than the drinkware brand, `haus.com` sells home equity
rather than goods, and `siete.com` is an online casino. That is a 1.6 percent
error rate on the part that could be checked, and about a quarter of the file
rests on judgement the recordings cannot confirm either way.

The boundaries are not sharp and no rule will make them sharp. A marketplace can
be read as ecommerce or as a platform, a direct-to-consumer brand as ecommerce or
as a storefront. The working distinction is that `ecommerce` sells many brands or
is a large retailer, `storefront` sells its own single brand, and `platform` is a
service whose product is other people's activity.

Nothing this repository publishes is grouped by type. The file exists for the
study output, which is regenerated locally and not committed. Treat any number
derived from it as resting on the paragraph above.

`data/corpus_manifest.csv` is the other file a re-recording touches, and it is
the one a reader without the 342 MB uses to check the numbers, so a pull request
that re-records the corpus should refresh it in the same commit.

```bash
pytest -m slow
```

Replays them all offline. Opt in, because a slow default is a suite people stop
running.

## Before you open a pull request

- `pytest` passes and `ruff check` is clean
- new behaviour has a test, and a bug fix has a test that fails without it
- no emoji, no em dashes, and nothing that reads as generated
- if you changed a verdict, say which real site made you notice
