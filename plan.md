# plan.md

Living state of the project. Update at the end of every session. Keep it short.
Decisions live in `CLAUDE.md`, progress lives here.

Last updated: 2026-08-30. Current phase: 6 closed except publication.

## Phase 0, decisions. DONE

Scope, name, rubric, buckets, output format and testing strategy are closed and
recorded in `CLAUDE.md`. Repository scaffold created.

## Phase 1, robots.txt and the Access score. IN PROGRESS

Goal: `geo-check example.com` reads robots.txt, classifies every agent into its
bucket, and prints an Access score with a letter grade.

- [ ] `fetch.py`: HTTP layer with timeouts, retries, a polite identifying
      user-agent, and a typed failure reason on every error path
- [ ] `robots.py`: protego wrapper, fake robots.txt detection, per-agent verdict
- [ ] `checks/access_*.py`: one file per Access criterion
- [ ] `scoring.py`: already written, verify against the rubric
- [ ] `cli.py`: minimal command, text output only
- [ ] Manual run against 5 sites known by hand, including one that blocks
      everything and one with no robots.txt

Done when: the Access score is correct on those 5 sites and every failure path
returns a reason instead of a traceback.

## Phase 2, page sampling and the Readability score. DONE

Goal: sample 5 pages from the sitemap and score Readability.

- [x] Sitemap discovery, robots.txt directive first, then `/sitemap.xml`
- [x] Sitemap index handling, one nesting level, capped at 5 nested fetches
      chosen by hash so a site that names its sitemaps by month is not sampled
      entirely from January
- [x] Deterministic sampling, ordered by `sha256(url)`, settled before a single
      request goes out
- [x] `checks/readability_*.py`: one file per criterion, eight of eight
- [x] JavaScript heuristic with thresholds measured across 22 live pages,
      recorded in `data/js_calibration.csv` and reproducible with
      `scripts/calibrate_js_threshold.py`
- [x] `llms.txt` fetched, with the same body over header rule as robots.txt
- [x] robots.txt is honoured for the tool's own user agent when sampling
      pages. The homepage is still always fetched, because without it there is
      nothing to report at all
- [x] Manual run: example.com (Access 90 A, Readability 22 F), observador.pt
      (75.33 B / 75.73 B), sapo.pt (48.67 D / 83.33 B), reddit.com (10 F /
      4.5 F), eco.sapo.pt (100 A / 79.63 B), excalidraw.com (100 A / 32 F, the
      single page application)
- [x] 96 tests, offline, under a second

Done when: Readability is correct on the same 5 sites plus one known
JavaScript-heavy single page application. Met. excalidraw.com scoring 100 on
Access and 32 on Readability is the case that shows why the two scores are
never averaged.

## Phase 3, output and fixes. DONE

- [x] JSON schema, versioned with a `schema_version` field
- [x] Markdown report generated from the JSON
- [x] Terminal text generated from the same JSON, so the three outputs cannot
      disagree about one run
- [x] Remediation templates, including exact robots.txt lines to add
- [x] One merged robots.txt block, so a site blocking both citation and user
      fetch crawlers gets a single thing to paste rather than two overlapping
      groups. Agents documented as ignoring robots.txt are left out of it
- [x] `--json` and `--output` flags write files
- [x] 109 tests, offline, under a second

Done when: a person who has never seen the tool can read the markdown report and
know what to change. Met. The report opens with what to change and closes with
what the tool cannot see.

## Phase 4, corpus and tests. DONE

- [x] `data/corpus_500.txt`, extended to 500 on 2026-08-30, every one
      checked to resolve before
      it went in. Where a category had more survivors than its target the trim
      was made by ordering on sha256 of the domain, and the 55 candidates that
      did not make the cut are listed at the bottom of the file
- [x] `build_site` takes a fetcher, so the suite replays recorded responses
- [x] `geo_check/fixtures.py` records and replays. A URL the fixture does not
      hold returns a failure with that reason rather than an invented 404
- [x] `scripts/refresh_fixtures.py` records and writes the outcome report
- [x] `data/golden_30.yaml`, 30 hard sites, every expectation traced by hand to
      the group that produced it
- [x] `tests/test_golden.py`, 33 assertions, 100 percent
- [x] `tests/test_robustness.py`, replays the corpus when it is recorded locally
      and skips when it is not
- [x] `data/robustness_report.json`, the per domain outcome

Two decisions taken here and recorded in `CLAUDE.md`, both with measurement
behind them.

Only the golden set ships in the repository, at 8 MB. The 500 site corpus would
be 208 MB, and truncating the pages was tested and rejected, because at a 300 KB
cap 6 of 12 domains moved their Readability score.

Completing means the tool handled the site, not that the site answered. About a
fifth of the corpus sits behind a bot manager that refuses a browser just as
readily.

One bug found, and it is the reason the golden set exists. protego matches user
agents by substring, so Wikipedia's group named `Fetch` captured
`Meta-ExternalFetcher`, and any site with `User-agent: bot` would have blocked
six citation crawlers in one line. Group selection moved into `robots.py`;
protego still answers every path question.

Done when: `pytest` runs offline, in seconds, and passes. Met, 149 tests in
under 12 seconds with no network.

## Phase 5, documentation. DONE

- [x] Renamed to `geo-check`. Package, command, skill and every reference. The
      reasoning is in `CLAUDE.md`
- [x] README rewritten, with a real run against nytimes.com near the top. That
      example was chosen deliberately: the New York Times
      configuration is deliberate and widely reported, so it demonstrates the
      tool reading a real setup correctly without making a smaller company the
      poster child for what is broken
- [x] `docs/RUBRIC.md`, the full rubric with the reasoning, including why
      training crawlers are worth zero and the two known weaknesses stated
      rather than hidden
- [x] `SKILL.md` finalised, with the things to get right when reporting
- [x] One line install verified in a clean virtual environment from a built
      wheel, under the new name

Done when: the floor is met. One line install that works first time, README with
the output near the top, MIT licence, and the tool not crashing on the first site
someone tries. Met.

## Phase 6, validation and launch. VALIDATED, NOT PUBLISHED

- [x] Ran the tool across the corpus, now 500 sites, and collected the numbers
      (`scripts/run_study.py`, aggregate in `data/study.json`, untracked)
- [x] Wrote `docs/VALIDATION.md`, the evidence that the tool works, and linked it
      from the README
- [ ] Publish the analysis. Not done and not for me to do. Publishing is outward
      facing and irreversible, so it stays with the maintainer.

**The analysis of what the 500 sites revealed about the web is held back
deliberately.** It is the maintainer's article and it is not written down here,
in `docs/`, in the README or in `data/study.json`, which is regenerated locally
and gitignored for exactly that reason.

This is a standing instruction, not a one time edit. A later session that runs
`scripts/run_study.py`, reads the numbers and writes them into the repository
would undo the decision without knowing there was one. Inside the repository the
500 site run has one job: proving the tool handles real input and gives correct
answers. What the run says about anyone's website belongs to the article.

What the repository does claim, and what `docs/VALIDATION.md` carries: 408
scored, 92 aborted with a logged reason, zero crashes, 9600 verdicts at 100
percent agreement with an independent reader, 182 block verdicts traced by hand,
and the three parser defects the validation found in this tool.

Hardened 2026-08-30, so the evidence survives a stranger checking it.

- [x] `data/corpus_manifest.csv`, 500 rows, 68 KB, the SHA-256 of every
      `robots.txt` as it was read. Built by `scripts/build_manifest.py`, checked
      against the live web by `scripts/verify_manifest.py`. All 25 in the
      reproducible sample still matched on the day it was written
- [x] The 92 aborts split by what they mean, 64 deliberate refusals, 20
      unreachable from here, 8 gone. One number read as one thing and the
      unreachable twenty may answer fine for someone else
- [x] `pytest -m slow` run to completion for the first time since the corpus
      doubled: 3 tests, all 500 replayed, and run again after every edit here
- [x] CI simulated from a clean checkout with no corpus fixtures, on 3.11 and
      3.14, through install, lint, test, wheel build and clean install. It had
      never been executed
- [x] Python 3.14 added to the matrix and the classifiers. `requires-python` has
      no upper bound and the maintainer's own environment is 3.14, so the tested
      range did not include the version being used

A five-lens adversarial audit of that commit then found more, and the largest was
not in any file.

- [x] **The git history stated everything the files no longer do.** Five earlier
      commits carried the withheld comparison in their diffs, and one carried the
      article's finding in its message body, which no edit to a working file can
      reach. Every removal was one `git log -p` away. History restarted from a
      single commit; the old history is bundled outside the repository
- [x] **The corpus was still partitioned, by structure.** Removing the printed
      counts left the sections that produced them, one of which was half the file
      on its own. It is now a single flat block ordered by sha256 of the domain,
      with site type in `data/corpus_categories.csv` across nine uneven types
- [x] `scripts/run_study.py` was silently broken by removing the count suffixes it
      parsed. Every domain fell into `unknown`. It reads the category file now and
      fails loudly instead
- [x] Ten documentation figures corrected against the data, including
      `excalidraw.com` at 32 not 30, the block wall share at 13 percent not 7, the
      hand-traced verdicts scoped to the 182 that score rather than implying all
      520, and the `Crawl-delay` bug described against the lines `eventbrite.com`
      actually writes
- [x] Two unsupported claims removed: three sites answering `GPTBot` with 200,
      which rests on data that does not ship, and two universal claims about
      competing tools
- [x] The JavaScript heuristic's fourth client rendered page, which neither cut
      catches, is now stated in `docs/RUBRIC.md` instead of being counted out

Four things were wrong and are fixed. `docs/VALIDATION.md` attributed five of the
seven 429s to Vercel; it is four Vercel, two istio-envoy, one Cloudflare. The
suite was documented at twelve seconds and measures fifteen. The
README called all 92 aborts CDN refusals. And `data/corpus_500.txt` still
carried the withheld comparison in its structure, with no sentence saying so.
## Open items

- **The user fetch bucket counts blocks that do not work.** Three of its five
  agents, `ChatGPT-User`, `Perplexity-User` and `Meta-ExternalFetcher`, are
  documented by their own vendors as ignoring robots.txt. The rubric still
  counts a block aimed at them. Written up in `docs/RUBRIC.md` as a known
  weakness rather than silently fixed, because changing the rubric is the
  maintainer's call. Scoring only the agents that honour robots.txt would give a
  truer number.
- **Publish to PyPI.** Needs `twine` and a PyPI token, which is the maintainer's
  to handle. The name is free and the wheel builds and installs clean.
- **Make the repository public.** It goes up private. Flipping it is one click.
- **Rename the working directory** from `geo-audit` to `geo-check`. Breaks the
  virtual environment, which has to be recreated.

Closed since these were written: the name (`geo-check`), the agent list
verification (all 25 checked against vendor documentation in phase 1), the
corpus (built and recorded in phase 4), and the JavaScript threshold
(measured across 22 pages in phase 2, recorded in `data/js_calibration.csv`).
