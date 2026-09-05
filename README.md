<h1 align="center">
  <img src="https://raw.githubusercontent.com/vasco-branco06/geo-check/main/assets/banner.svg" alt="geo-check" width="100%">
</h1>

<p align="center">
  <a href="https://github.com/marketplace/actions/geo-check"><img src="https://img.shields.io/badge/GitHub%20Marketplace-geo--check-24292f?logo=github&logoColor=white" alt="On the GitHub Marketplace"></a>
  <a href="https://github.com/vasco-branco06/geo-check/actions/workflows/ci.yml"><img src="https://github.com/vasco-branco06/geo-check/actions/workflows/ci.yml/badge.svg" alt="CI status"></a>
  <img src="https://img.shields.io/badge/licence-MIT-1f6feb" alt="MIT licence">
  <img src="https://img.shields.io/badge/python-3.10%2B-1f6feb" alt="Python 3.10 or newer">
  <img src="https://img.shields.io/badge/audited-906%20sites-6f42c1" alt="Audited across 906 sites">
  <img src="https://img.shields.io/badge/LLM%20calls-none-2da44e" alt="No LLM calls">
</p>

<p align="center">
  <b>Check whether a website is reachable and readable by AI crawlers, and score it.</b><br>
  Two scores, never averaged. Blocking model training costs no points.
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/vasco-branco06/geo-check/main/assets/output.png" alt="geo-check auditing nytimes.com: Access 56 out of 100 grade D, Readability 82.5 out of 100 grade B, three of six citation crawlers allowed, and the exact robots.txt lines to add." width="624">
</p>

<p align="center">
  <sub>A real run, replayed from a recording committed to this repository. Trimmed for height.</sub>
</p>

## Try it

**As a Claude Code skill.** The `SKILL.md` at the root of this repository is the
skill, and one command installs it:

```bash
npx skills add vasco-branco06/geo-check
```

**As a command line tool**, which is also what the skill runs:

```bash
pip install git+https://github.com/vasco-branco06/geo-check
geo-check your-domain.com
```

Python 3.10 or newer and open network access. No API key, no account, no model
call. It does not run inside sandboxes that only reach an allowlist of domains.

> Not on PyPI yet, so the install comes from git for now.

Or run it without installing anything: fork this repository, open the **Actions**
tab, choose **audit a site** and press Run. The report lands in the run summary.

## What GEO is, and why it matters

Generative Engine Optimization. The question is no longer only whether Google
lists you, it is whether ChatGPT, Claude, Perplexity and AI Overviews can find
you, read you, and quote you.

Most advice treats AI bots as one thing. They are not, and the confusion is
expensive. OpenAI alone runs three crawlers that do different jobs:

| Crawler | What it does | Blocking it costs you |
| --- | --- | --- |
| `GPTBot` | Collects pages for model training | Nothing in ChatGPT results |
| `OAI-SearchBot` | Decides whether ChatGPT can cite you | Your place in ChatGPT results, entirely |
| `ChatGPT-User` | Fetches a page someone asked about | Nothing, it is documented as ignoring robots.txt |

Those first two sit one line apart in a `robots.txt` file. Anthropic, Perplexity,
Google and Apple all split their crawlers the same way.

Some sites block the first on purpose and say so in public. Others opt out of
training and remove themselves from ChatGPT at the same time without meaning to,
and from outside a robots.txt file you cannot tell which is which. What you can
tell is exactly which lines are there and what each one costs, which is what this
prints.

## What makes this one different

**Two scores, never averaged.** `excalidraw.com` scores 100 on Access and 32 on
Readability. It is wide open to every crawler and unreadable by all of them. An
average of 66 would describe nothing true about that site and would hide the one
thing worth acting on, so the two never collapse into one figure.

**Training crawlers are worth zero points, on purpose.** Blocking model training
is a legitimate business decision, not a mistake. A newspaper protecting its
archive has done nothing wrong, and a tool that deducts points for it is not
measuring, it is lobbying. Training appears as one informational line and never
touches either score.

**Nothing is scored by a model.** No LLM sits in the scoring path. Every point
comes from a rule you can read in
[docs/RUBRIC.md](https://github.com/vasco-branco06/geo-check/blob/main/docs/RUBRIC.md)
and trace to the line of `robots.txt` or markup that earned it, so the same site
scores the same twice and a score you disagree with is an argument you can have.

**Validated against 906 real sites, and the validation found bugs here first.**
744 scored, zero crashes, and no abort without a reason. Every `robots.txt` was
then read three ways and compared per agent, 17025 verdicts, agreeing 100 percent
with an independent reader written from RFC 9309. Three implementations agreeing
proves consistency and not correctness, so the 289 verdicts that carry a score
were each traced by hand to the group that produced them.

It caught three real defects in this tool before anyone else could:

| Defect | What it would have done |
| --- | --- |
| User agents matched by substring | A site writing `User-agent: bot` would have silently blocked six citation crawlers at once |
| Groups declaring the same agent not merged | A site that contradicts itself got the first rule instead of the merge RFC 9309 requires |
| A bare `Crawl-delay` closing nothing | One site's `CCBot` inherited a `Disallow` aimed at a marketing crawler |

The 342 MB of recordings behind that are too large to ship, so
[data/corpus_manifest.csv](https://github.com/vasco-branco06/geo-check/blob/main/data/corpus_manifest.csv)
carries the SHA-256 of every `robots.txt` as it was read, all 906 rows, dated.
`python scripts/verify_manifest.py --sample 25` fetches them today and tells you
which still match. The evidence, and what it does not prove, is in
[docs/VALIDATION.md](https://github.com/vasco-branco06/geo-check/blob/main/docs/VALIDATION.md).

## Keep it from regressing

A site is one deploy away from losing its AI visibility, and nobody notices for
months. Add this to any workflow and a bad `robots.txt` fails the build:

```yaml
- uses: vasco-branco06/geo-check@v0
  with:
    domain: your-domain.com
    fail-under-access: 60
    fail-under-readability: 50
```

Both thresholds are optional. Leave them out and it reports without failing. The
full report goes into the job summary, and the scores come back as outputs you
can read in later steps.

It is on the [GitHub Marketplace](https://github.com/marketplace/actions/geo-check).

## The two scores

**Access** is whether AI systems can reach the site at all. Citation crawlers
allowed (50), user fetch crawlers allowed (20), sampled pages reachable without
a login wall (15), sitemap declared and reachable (10), no noindex (5).

**Readability** is whether an AI system can make sense of a page once it has it.
Content in the raw HTML without JavaScript (30), valid JSON-LD (20), heading
structure (15), title and meta description (10), author and dates (10),
canonical (5), llms.txt (5), answer shaped content (5).

Grades: 90 and above A, 75 to 89 B, 60 to 74 C, 40 to 59 D, below 40 F.

Three critical failures cap the Access score. All citation crawlers blocked caps
it at 20. A blanket `Disallow: /` caps it at 10. A homepage that does not return
200 aborts the run, because there is nothing honest to score.

The full rubric, with the reasoning and the weaknesses it still has, is in
[docs/RUBRIC.md](https://github.com/vasco-branco06/geo-check/blob/main/docs/RUBRIC.md).

## Questions people actually ask

**Isn't this just reading robots.txt?**
That is one of the thirteen checks, and it is the one most tools get wrong.
Matching a crawler to a group is a specification, not a substring search, and
following RFC 9309 properly is where all three bugs found here lived. The other
twelve read the sitemap, `llms.txt`, and five sampled pages for structure,
JSON-LD, headings, authorship and whether the content survives without
JavaScript.

**Why doesn't blocking model training cost points?**
Because it is a decision, not a defect. Plenty of publishers block training
deliberately and are right to. A tool that deducts for it has an opinion about
your business model rather than a measurement of your site. It is reported as one
line so you can see it, and it moves neither score.

**Why two scores instead of one?**
Because they fail independently and different people fix them. A site can be
perfectly reachable and impossible to read, or beautifully structured and blocked
at the first line of `robots.txt`. One number hides whichever half is broken.

**Does it work if I am behind Cloudflare?**
It reads what your `robots.txt` and markup say. It cannot see a bot manager
returning 403 to crawlers while serving you fine, and it says so in the report
rather than scoring around it. If the homepage refuses this tool, the run aborts
with the reason instead of inventing a score.

**Why trust a number a heuristic produced?**
Only trust the ones that are measured, and the report tells you which is which.
The JavaScript check is a heuristic with thresholds taken from 22 live pages, and
[docs/RUBRIC.md](https://github.com/vasco-branco06/geo-check/blob/main/docs/RUBRIC.md)
names the page in that sample it gets wrong. The `robots.txt` verdicts are not a
heuristic, and they carry most of the Access score.

**Do I need llms.txt?**
Probably not urgently. It is a proposal rather than a standard and no major
assistant is documented as requiring it, which is why it is worth 5 points out of
100 here and not more.

## What this does not do

It does not detect blocking at the CDN or WAF level. Your robots.txt can say yes
while Cloudflare returns 403 to AI crawlers, and this tool will not see it.

It does not render JavaScript. The raw HTML check measures how much readable text
arrives in the initial response and how much of that response is script. The
thresholds were measured across 22 live pages rather than chosen, and both the
numbers and the script that produced them are in the repository.

Answer shaped content is detected structurally. The check can see that a page has
an ordered list of five steps and that the prose is broken into sections. It
cannot see whether either is any good.

It does not measure whether AI assistants actually cite you. That is a different
and much larger problem.

## The crawler list

32 user agents, each with its vendor, its bucket, whether the vendor
documents it as honouring `robots.txt`, and a link to that documentation.
[docs/CRAWLERS.md](https://github.com/vasco-branco06/geo-check/blob/main/docs/CRAWLERS.md)
explains how the buckets work and why six of the on demand fetchers are
reported as ignoring a block aimed at them.

The list moves. Pull requests adding or correcting an entry, with the vendor's
own documentation URL, are the most useful contribution you can make.

## Contributing

Adding a check is one file in `src/geo_check/checks/` and one line in the
registry.

```bash
pip install -e ".[dev]" && pytest
```

178 tests, offline, about twenty five seconds. The suite never touches the network.
[CONTRIBUTING.md](https://github.com/vasco-branco06/geo-check/blob/main/CONTRIBUTING.md)
has the rest: how a check is written, how the golden set works, how to record
fixtures, and why the recorder is deliberately slow.
[SECURITY.md](https://github.com/vasco-branco06/geo-check/blob/main/SECURITY.md)
carries one known and unfixed issue worth reading before you pipe this tool's
output into an agent.

## Licence

MIT.
