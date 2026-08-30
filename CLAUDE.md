# CLAUDE.md

Permanent memory for this repository. Read this file and `plan.md` before doing
anything else in a session. Update both at the end of every working session.

## What this is

`geo-check` is a Claude Code skill. It checks whether a website allows AI
crawlers and scores it against a documented rubric.

Named 2026-08-30, after measurement rather than preference, and renamed once
more the same day.

First pass: `geo-audit` was taken on PyPI since June 2026 by a tool doing almost
the same thing, and PyPI normalises names, so `geo_audit` and `geoaudit` were
gone with it. The fallback in `plan.md`, `ai-crawler-audit`, was taken on GitHub.
`aeo-audit` and `ai-visibility` turned out to be published packages too. That
left `crawlable`, which the project carried briefly.

Second pass, and the reason it is worth writing down. The maintainer asked for
`awesome-geo`. Checking it turned up three GitHub repositories already using that
exact name, all curated lists about Generative Engine Optimization, with 136, 119
and 33 stars. A fourth repository with that name, and the only one that is not a
list, would have lost the search it was meant to win. `geo-check` is free on PyPI
and has no exact name match on GitHub. It keeps the GEO the maintainer wanted and
says what the tool does.

The distribution, the command and the repository are `geo-check`. The importable
package is `geo_check`, because module names cannot take hyphens. A blind find
and replace across the two breaks imports.

Public repository, MIT licence. Everything in the repository is written in
English. Conversation with the maintainer happens in European Portuguese.

## Who I work with

Vasco Caldeira Branco. Basic technical level, learns Python mainly to read code.
Explain technical decisions in plain language before executing them. Do not
assume knowledge he has not demonstrated.

## Working rules

- When asked to think, plan or discuss, produce text only. No files, no code.
- Present a short plan and wait for approval before building any phase.
- No phase starts before the previous one is closed and tested.
- Do not reopen closed decisions unless the maintainer reopens them, or a new
  fact makes them wrong (a crawler renamed, a library deprecated). Say so and
  explain.
- Report limitations honestly. If a check is a heuristic that can be wrong, the
  report and the docs say so.
- No emojis. No em dashes. Strip AI provenance metadata from generated files.

## Closed decisions

**Runtime.** Claude Code skill, runs on the user's machine. Needs open network
access and Python 3.10 or newer. It does not run inside the claude.ai sandbox,
which only reaches an allowlist of domains. The README states this explicitly.

**Input.** One domain per run, plus 5 pages sampled from the sitemap.
`--pages N` overrides the count, default 5.

**Two separate scores, never averaged.** Access and Readability, each 0 to 100,
each with its own letter grade. Grades: 90+ A, 75-89 B, 60-74 C, 40-59 D,
below 40 F.

**Three crawler buckets.** `training`, `citation`, `user_fetch`. Defined in
`src/geo_check/data/agents.json`.

**Access rubric, 100 points.** Citation crawlers allowed 50, split evenly across
the citation agents. User-fetch crawlers allowed 20. Sample pages return 200
without a login wall 15. Sitemap declared and reachable 10. No noindex, in meta
robots and in the X-Robots-Tag header, 5.

Training crawlers are worth zero points. They appear as an informational line,
`Training posture: open / partial / closed`. Blocking training is a legitimate
business decision, not an error, and must not lower the score. This is the most
opinionated call in the project and it is deliberate.

**Readability rubric, 100 points.** Content present in raw HTML without
JavaScript 30. Valid JSON-LD with a recognised @type 20. Correct heading
structure 15. Title and meta description present, unique across sample pages,
reasonable length 10. Author and publication or modification dates identifiable
10. Canonical present and consistent 5. llms.txt present with real content 5.
Answer-shaped content 5.

**Critical failures that cap the score.** All citation crawlers blocked caps
Access at 20 and flags CRITICAL. `User-agent: *` with `Disallow: /` caps Access
at 10. Homepage returning anything other than 200 aborts the run and returns an
error instead of a score.

**No robots.txt means everything is allowed.** Full points on that dimension,
plus an informational note. The parser must detect fake robots.txt: a request to
`/robots.txt` returning 200 with HTML. Check the content type and whether the
body looks like robots syntax before trusting it.

Amended 2026-08-30, with evidence. The body decides, the content type only
corroborates. `sapo.pt` serves a valid robots.txt under
`Content-Type: text/html`, and treating the header as a veto reported that site
as having no robots.txt at all, which inflated its score. A body that starts
with HTML markup is rejected; a body full of robots directives is accepted
whatever the header claims.

**The analysis stays out of the repository.** What the 500 site run says about
the web is the maintainer's article. Inside the repository that run proves the
tool works and nothing else: `docs/VALIDATION.md` carries outcomes, agreement
rates and the defects the validation found, and no conclusion about anyone's
website. `data/study.json` is regenerated locally and gitignored.

This is standing, not a one time edit. Running `scripts/run_study.py` and writing
its numbers into the repository would undo the decision without knowing there was
one.

**Output.** JSON is the real result and the source of truth. The markdown report
is generated from that JSON.

Extended 2026-08-30: the text printed in the terminal is rendered from the same
payload. Two renderers reading different sources would eventually disagree about
the same run, and in a tool whose subject is accuracy that is the worst place to
carry a bug.

**Fixes, not just findings.** Every failed check emits a concrete remediation,
including the exact robots.txt lines to add. Template based.

**robots.txt parsing uses `protego`.** Do not write a custom parser. Allow and
Disallow precedence and wildcards are where silent bugs live.

Amended 2026-08-30, with evidence, and the golden set found it. protego matches
user agents by substring, because it is built for Scrapy, where the caller hands
it a whole User-Agent header. We hand it a bare product token, and substring
matching then gives wrong verdicts: Wikipedia has a group named `Fetch`, aimed
at a download manager, and it captured `Meta-ExternalFetcher`. A site with
`User-agent: bot` would have silently blocked GPTBot, Googlebot, Bingbot,
PerplexityBot, OAI-SearchBot and Claude-SearchBot in one line.

So group selection moved into `robots.py`, using the prefix rule the
specification describes, and only the selected group, renamed to `*`, is handed
to protego. Every path question stays with protego. It is simply no longer asked
which crawler the rules were for.

Amended again 2026-08-30, found by the accuracy harness. RFC 9309 section 2.2.1
says every group declaring the winning user-agent value is merged into one, and
we were taking the first. Files contradict themselves more often than you would
think: `contasconnosco.pt` blocks `CCBot` at line 42 and allows it at line 74.
Taking the first says blocked, taking the last says allowed, and both are wrong.
Merged, the two rules tie on length, Allow wins, and the answer is allowed.
Merging applies only to the winning value, so `Google` and `Googlebot` stay
separate groups and the longer one still wins.

**Agent list lives in `src/geo_check/data/agents.json`**, versioned, with a review
date and the official documentation URL for each agent. Never hardcoded in the
code. It sits inside the package, not in a top level `data/` directory, because
a wheel does not carry files from outside the package and `pip install` would
otherwise ship a tool that cannot find its own agent list.

**JavaScript check is a heuristic.** It compares the amount of text in the raw
HTML against a threshold. It is not real rendering. The README and the report
say so.

Thresholds set 2026-08-30 from measurement, not taste. `scripts/calibrate_js_threshold.py`
sampled 22 live pages into `data/js_calibration.csv`. Two cuts came out of it:
text below 500 characters, where three of the four known client rendered pages
measured 32, 86 and 427 and nothing server rendered fell below 1463; and a
script to text ratio above 100, which caught two news homepages at
244 and 335 while every genuinely server rendered page sat below 35.

The fourth client rendered page, `jsonformatter.org`, is caught by neither cut:
7773 characters of static text around the app and a script to text ratio of 0.27.
The check is wrong about it, `docs/RUBRIC.md` says so, and the CSV labels it. Do
not quietly drop it from the count to make the rule look clean, which is what the
first write-up did. A third
signal, an empty mount point, was tested and dropped for finding nothing the
text rule had not already found.

**Answer shaped content is detected structurally.** The five points go to sites
whose pages carry at least three of six shapes: numbered steps, a comparison
table, a question and answer block, a definition list, an attributed quote, a
summary box. The shapes come from the extractable content patterns in the `aeo`
skill. The check reads markup, so it can see an ordered list of five steps and
cannot see whether the steps are any good. The report says exactly that.

## Out of scope for v1

CDN or WAF level blocking detection. Real JavaScript rendering. Measuring actual
citations in ChatGPT, Perplexity or AI Overviews. Batch mode across many
domains. Dashboard. History and run comparison. Plugin system.

The v1 report explicitly states that it does not check CDN level blocking.

## Testing strategy

Robustness corpus of 500 real sites in `data/corpus_500.txt`, mixing ecommerce,
small and micro storefronts, news and media, SaaS and agencies, personal blogs,
and large well known sites across sectors. Extended to 500 on 2026-08-30.

**The fixtures do not ship, so the fingerprints do.** 500 sites of recorded HTML
is 208 MB and stays out of the repository, which would leave every published
figure resting on files one machine holds. `data/corpus_manifest.csv` carries one
row per domain with the read timestamp, the outcome and the SHA-256 of the
`robots.txt` body, and `scripts/verify_manifest.py` re-fetches and re-hashes with
the same normalisation. Added 2026-08-30. A study whose numbers a reader cannot
check is a claim, not evidence, and this project's whole subject is accuracy.

The hash covers the decoded body re-encoded as UTF-8, because recording keeps
text rather than bytes. That is why the checker is a script: a documented
normalisation the reader has to reproduce by hand is a normalisation that will be
reproduced wrong.

How the 500 divide, and what that division shows, is the maintainer's article
and is not stated anywhere in this repository. That includes per category counts:
a set of counts that partitions the corpus states the division by arithmetic even
when no sentence does, which is how it survived the first two attempts to remove
it. Describe the mix, never partition it.

**The corpus file carries no sections.** `data/corpus_500.txt` is one flat block
ordered by sha256 of the domain, and site type lives in
`data/corpus_categories.csv`. Changed 2026-08-30, on the third attempt, because
the first two removed the words and left the structure. Sections have sizes, and
sizes are counts whether or not anybody prints them; a section that is a round
fraction of the file needs no arithmetic at all. Do not reintroduce section
comments to that file, however convenient they look, and when writing down that
this was fixed, describe the shape of the leak rather than quoting it. The note
has reintroduced it once already.

**Publishing platform is a dimension, not a category.** Making it a category
produced an artifact: forty domains read out of a Shopify directory came back
100 percent Shopify with 100 percent llms.txt adoption, which is what that
platform ships rather than what small businesses do. Reported as micro
businesses it would have credited a hosting platform's work to company size and
distorted an adoption figure. So platform is now detected for all 500 and
reported across every category, which is a better comparison and cannot be gamed
by where the domains came from.

Sourcing non Shopify small businesses was attempted and failed. A marketplace of
850 independent brands does not resolve, two published store lists
return 404, and category searches return aggregators such as TheFork and Time
Out rather than the businesses' own domains. The Shopify directory worked only
because it publishes a sitemap. Written down so nobody repeats the search
expecting a different result.

**Sweeping many sites is a request pattern, and the pattern gets measured too.**
Recording forty Shopify storefronts with eight workers had Cloudflare answer 429
to every one of them for the next half hour, including one that had answered 200
an hour earlier. Those are not sites blocking anything, that is the sweep
blocking itself, and writing them down as aborted would have put a fabricated
number in the study. `fetch.py` now backs off twenty seconds on a 429 and
honours `Retry-After`; `refresh_fixtures.py` defaults to four workers and
staggers their starts. Responses are saved as
fixtures in the repository and tests run against those files, offline. Target:
above 95 percent completing, the rest failing with a logged reason. Failing with
a reason counts as working.

Golden set of 30 sites verified by hand, chosen because they are hard: no
robots.txt, wildcards, conflicting Allow and Disallow, blanket blocks, llms.txt
present, Cloudflare generated robots.txt. These require 100 percent accuracy.

A separate script refreshes fixtures against the live web, so the test suite
never hits real sites during development.

**Accuracy is measured separately from completion**, added 2026-08-30, because
they were being confused. Completion says the tool does not fall over.
`scripts/verify_accuracy.py` reads every robots.txt three ways: the tool, the
standard library, and a literal reader written from the specification that
shares no code with either. Disagreement with the standard library is expected
and is evidence for the tool, since it carries the same substring matching bug
we fixed. Three implementations agreeing proves consistency, not correctness,
so the number worth publishing is the count of block verdicts traced by hand to
the robots.txt line that produced them.

Amended 2026-08-30, with measurement. Only the golden set ships in the
repository, at 8 MB. The 500 site corpus is 208 MB, and truncating the
pages was tested and rejected: at a 300 KB cap, 6 of 12 domains changed their
Readability score, one of them by 15 points. Access is unaffected, because it
rests on robots.txt. So `tests/fixtures/corpus/` is gitignored, recorded
locally, and the robustness test skips when it is absent. What the repository
does carry is `data/robustness_report.json`, the per domain outcome, which is
the evidence and is small.

Amended 2026-08-30. Completing means the tool handled the site, not that the
site answered. Roughly a fifth of the corpus sits behind Cloudflare, Akamai,
DataDome or CloudFront, which refuse a browser as readily as they refuse this
tool. That is not a tool failure and it must not be reported as those sites
blocking AI crawlers: three of them were observed allowing a GPTBot user agent
while refusing everything else. The 95 percent target is measured against
crashes and reasonless aborts, which is what the rest of that paragraph already
says.

## Extensibility

Every check follows the contract in `src/geo_check/models.py`: an identifier, a
category, a weight, and a function taking a context and returning a result with
evidence and a fix. Adding a GEO or SEO check later is one file plus one line in
the registry. Do not build a plugin system or entry points in v1.

## Project goal

The maintainer wants real visibility for this repository, including as portfolio
evidence. GitHub stars come from distribution, not code quality. The 500 site
sweep produces a publishable study, which the maintainer writes and publishes
himself. Its thesis is not recorded here, deliberately. That study launches the
tool, and the tool proves the study. Treat them as one project.

The README is a first class artifact and gets written early, not at the end.

Non-negotiable floor: one line install that works first time, README with a
picture of the output near the top, MIT licence, and the tool not crashing on
the first site someone tries.

Above that floor, do not polish. Test coverage beyond the target, elegant
refactors and premature architecture return nothing and delay the launch. If the
maintainer starts asking for extra polish, remind him of this.
