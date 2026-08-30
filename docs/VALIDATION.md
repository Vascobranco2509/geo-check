# Validation

What this document is: the evidence that `geo-check` does what it says. Not a
study of the web. Every number here is about the tool.

Measured 2026-08-30. The aggregation scripts are
[scripts/run_study.py](../scripts/run_study.py) and
[scripts/verify_accuracy.py](../scripts/verify_accuracy.py), and both run offline
against recorded responses, so this is reproducible rather than remembered.

## It survives the real web

500 real sites, recorded and replayed.

| | Sites |
| --- | ---: |
| Audited and scored | 408 |
| Aborted with a logged reason | 92 |
| Crashed | 0 |
| Aborted without an explanation | 0 |

The per site outcome is in
[data/robustness_report.json](../data/robustness_report.json).

Completing means the tool handled the site, not that the site answered. None of
the 92 is the tool failing, but they do not all mean the same thing, and a single
number hides that:

| | Sites | What came back |
| --- | ---: | --- |
| Refused deliberately | 64 | 61 x 403, and one each of 401, 406 and a 202 challenge page |
| Unavailable to this client | 20 | 7 x 429, 8 timeouts, 5 connection errors |
| Gone | 8 | 7 x 404 and one 410 |

The middle row is the one to be careful with. Those twenty may answer perfectly
for a reader on a different network, and nothing in this run proves otherwise.
The first row is a site turning away an automated client on purpose, usually
through a CDN or a bot manager.

**A 403 is not evidence that a site blocks AI crawlers.** A bot manager decides
on address reputation as much as on user agent, and refuses a browser from a data
centre just as readily. From outside you cannot separate an AI policy from an
infrastructure policy, so the tool reports the refusal and declines to interpret
it.

**HTTP 429 is ambiguous in both directions.** The seven answer from three
infrastructures, four from Vercel, two from istio-envoy and one from Cloudflare,
all of which rate limit by IP across every site they serve. So a 429 can mean the
site's policy or it can mean our own address. Re-checked hours after the run,
individually rather than in parallel, all seven still returned 429, which rules
out a burst from the recording but does not separate the two readings. They are
counted as aborted and excluded from any claim about a site.

## The answers are right

Every `robots.txt` in the corpus was read three ways and compared per agent, 9600
verdicts across the 384 sites that have a real one. Of the other 116, 92 never
reached `robots.txt` and 14 returned a non-200 for it. The remaining 10 answered
with HTTP 200 and a body carrying no directives: five served markup instead of
`robots.txt`, including `linkedin.com`, which returned a reCAPTCHA challenge
page, and `abreu.pt`, which returned 68 KB of HTML; three served an empty file;
and two served a valid `text/plain` file of nothing but comments. Only the first
five are a site answering the wrong thing. The other five are legitimately
permissive, and all ten are treated the same way, as a site with no rules.

- **the tool**
- **the Python standard library**, `urllib.robotparser`, on the raw file
- **a literal reader** written from RFC 9309, sharing no code with either

| | Agreement with the tool |
| --- | ---: |
| Literal reader | 100.00% |
| Standard library | 99.96% |

The four standard library disagreements are all the same fault, and it is the
library's: it matches user agents by substring, so a site with a group named
`Fetch`, aimed at a download manager, has that group applied to
`Meta-ExternalFetcher`. The tool gets all four right.

**Three implementations agreeing proves consistency, not correctness.** So the
work that actually establishes accuracy was done by hand: all 182 scoring block
verdicts across 37 sites were traced to the `robots.txt` group that produced
them, and none was unexplained. Scoring means the citation and user fetch
buckets, 77 and 105 verdicts. The same 37 sites also block training crawlers 338
times, which was not traced by hand, because a training block earns and costs
nothing and cannot move a score. A separate sample of 25 sites the tool reports as fully
open was checked for false negatives and found clean.

That distinction is the point. An automated agreement rate is easy to produce and
easy to fool. The number worth trusting is the one a person checked.

The full comparison is in
[data/accuracy_report.json](../data/accuracy_report.json).

## It found three bugs in itself

This is the strongest evidence the validation is worth running, and each one
would have produced confidently wrong answers in the field.

**User agents matched by substring.** `protego`, which decides path questions
here, matches user agents the way Scrapy needs and this tool does not: it is
handed a whole `User-Agent` header, we hand it a bare product token. Wikipedia
has a group named `Fetch` that was being applied to `Meta-ExternalFetcher`, and
worse, any site writing `User-agent: bot` would have silently blocked GPTBot,
Googlebot, Bingbot, PerplexityBot, OAI-SearchBot and Claude-SearchBot in one
line. Group selection moved into `robots.py` using the prefix rule the
specification describes; `protego` still answers every path question.

**Groups declaring the same agent not merged.** One site declares `CCBot` twice
and contradicts itself, blocking it on one line and allowing it thirty two
lines later. We took the first group, the standard library took the last, and RFC 9309
section 2.2.1 says both are wrong: merge every group declaring the winning agent,
after which the two rules tie on length and Allow wins.

**A bare `Crawl-delay` closing nothing.** One site writes `User-agent: CCBot`
and a `Crawl-delay`, then `User-agent: AhrefsBot` and a `Crawl-delay`, then
`User-agent: Balihoo` and a `Disallow: /`. Only `Allow` and `Disallow` were
treated as ending a run of agent lines, so all three agents ran together into
one group and `CCBot` inherited a rule aimed at a marketing crawler. Any line
that is not a user-agent line closes the block.

All three are fixed, each with regression tests, and the independent reader was
corrected from the same paragraph of the specification rather than from making it
agree with us.

## The golden set

Thirty sites chosen because they are hard, replayed from fixtures committed to
this repository, and required to be exactly right.

The shapes covered: no `robots.txt` at all, a homepage served at `/robots.txt`,
a blanket `Disallow: /`, a blanket block that names exceptions, wildcards,
conflicting `Allow` and `Disallow`, Cloudflare generated files, `llms.txt`
present, nested sitemap indexes, a single page application, training blocked with
citation left open, and four different ways for a run to abort.

Every expectation in [data/golden_30.yaml](../data/golden_30.yaml) was traced by
hand to the `robots.txt` group that produced it. Two shapes from the original
list are absent, and both absences are findings rather than gaps in the search;
the file says which and why.

`pytest` runs the whole suite offline in about fifteen seconds and never touches
the network.

## What this does not prove

**That the scores are the right scores.** The rubric is a set of weights chosen
by a person. What is validated here is that the tool applies them correctly and
consistently, not that a site scoring 80 deserves 80. The reasoning behind each
weight is in [RUBRIC.md](RUBRIC.md), including two weaknesses it still has.

**That a site is or is not blocked at the edge.** The tool reads `robots.txt` and
markup. A site can pass every check and still return 403 to AI crawlers in
practice, and 64 sites in this run refused this one outright.

**That the heuristics are right about any individual site.** The JavaScript check
measures text volume and script weight rather than rendering, with thresholds
measured across 22 live pages and recorded in
[data/js_calibration.csv](../data/js_calibration.csv). The sectioning measure
uses thresholds from 12301 blocks across 868 pages, in
[data/block_calibration.csv](../data/block_calibration.csv). Both will misjudge
individual pages.

**That `robots.txt` says today what it said then.** These files change. Every
claim here is dated, and
[data/corpus_manifest.csv](../data/corpus_manifest.csv) carries the SHA-256 of
each one as it was read, so a change is visible rather than assumed.

**That blocking a fetcher achieves anything.** `Perplexity-User`, `ChatGPT-User`
and `Meta-ExternalFetcher` are documented by their own vendors as ignoring
`robots.txt`. The tool reports that plainly, and the rubric still counts the
block, which is a known weakness written up rather than buried.

## Reproducing it

```bash
pip install -e ".[dev]"
```

```bash
pytest
```

The offline suite, including the golden set. 164 tests, about fifteen seconds,
no network.

```bash
python scripts/refresh_fixtures.py --out tests/fixtures/corpus
```

Records the 500 sites. Touches the live web and takes about forty minutes. The
fixtures are not committed, because 500 sites of real HTML is 208 MB and
truncating them was measured and rejected: at a 300 KB cap, 6 of 12 test domains
moved their Readability score.

```bash
python scripts/verify_accuracy.py --out data/accuracy_report.json
```

```bash
pytest -m slow
```

Replays all 500 offline, in five to ten minutes depending on the machine. Opt
in, because a slow
default is a suite people stop running.

## Checking the numbers without the fixtures

The 208 MB of recordings stay out of the repository, so the figures above rest on
files one machine holds. [data/corpus_manifest.csv](../data/corpus_manifest.csv)
is the part that fits: 500 rows, one per domain, each naming when it was read,
what the run did with it, and the SHA-256 of the `robots.txt` body. 394 domains
carry a hash; the other 106 either aborted before that point or answered
`/robots.txt` with a non-200. A hash records what came back rather than what it
should have been, so the pages that were not `robots.txt` are fingerprinted too.

One limit worth stating, because it is the kind of thing a manifest can hide. A
hash only proves a match for a file that is stable. `linkedin.com` returned a
challenge page carrying a per-request token, so that row will never report
`MATCH` however faithfully it was recorded. The row still fixes the size and the
date; it does not let you reproduce the body.

```bash
python scripts/verify_manifest.py --sample 25
```

Fetches those files now and reports `MATCH`, `CHANGED` or `UNREACHABLE` per
domain, hashing exactly the way the recording did. Name domains as arguments to
check specific ones. The sample is ordered by the SHA-256 of the domain, so it
is reproducible and cannot be steered towards the rows that happen to still
match. All 25 matched on 2026-08-30.

A `CHANGED` row is not a failure. Sites edit `robots.txt`, which is why every row
is dated. What the manifest rules out is a number that was never measured, and it
covers all 500 including the 92 that never scored, so nothing was quietly
dropped.

The hash is taken over the decoded body re-encoded as UTF-8, because recording
keeps text rather than bytes. The verifier applies the same normalisation, which
is why it is a script and not a paragraph asking you to guess.

```bash
python scripts/build_manifest.py
```

Rebuilds the manifest from the recordings. It should reproduce the committed file
byte for byte.
