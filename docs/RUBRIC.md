# The rubric

Two scores, each from 0 to 100, each with its own letter. They are never
averaged.

Grades: 90 and above A, 75 to 89 B, 60 to 74 C, 40 to 59 D, below 40 F.

## Why two scores and not one

A site can be wide open and unreadable. It can also be beautifully structured
and blocked at the door. Those are different problems, they have different
fixes, and the people who fix them are often different people.

`excalidraw.com` scores 100 on Access and 32 on Readability. Averaging gives 66,
a C, which describes nothing that is true about that site and hides the one
thing worth acting on.

Any single number throws away the distinction that matters most here: reachable
and unreadable is a different job, for different people, than readable and shut
out.

## The three crawler buckets

Vendors run separate crawlers for separate jobs, and they are controlled
separately in robots.txt. Treating them as one thing is the mistake this whole
project exists to correct.

**Citation.** Feeds retrieval and citation in AI answers. `OAI-SearchBot`,
`Claude-SearchBot`, `PerplexityBot`, `Googlebot`, `Bingbot`, `Applebot`.
Blocking these removes the site from AI results. Worth 50 points.

**User fetch.** Retrieves one page on demand, when someone pastes a link or asks
about a URL. `ChatGPT-User`, `Claude-User`, `Perplexity-User`, `MistralAI-User`,
`Meta-ExternalFetcher`. Worth 20 points.

**Training.** Collects pages for model training. `GPTBot`, `ClaudeBot`,
`Google-Extended`, `CCBot` and ten others. Worth nothing, and that is the next
section.

## Training crawlers are worth zero points

This is the most opinionated call in the project.

Blocking model training is a legitimate business decision. A newspaper that does
not want its archive turned into training data has made a choice about its own
property, and it is not a mistake. A tool that deducts points for it is not
measuring anything, it is lobbying.

The confusion this rubric is built to clear up is that most people blocking
`GPTBot` believe they are opting out of training and nothing else. They are
right, and that is the point: `GPTBot` is training, `OAI-SearchBot` is search.
Blocking the first costs you nothing in ChatGPT results. Blocking the second
removes you from them entirely. The two live one line apart in a robots.txt file
and are constantly confused, including in published guidance.

So training appears as a single informational line, `Training posture: open,
partial or closed`, and never touches either score.

## Access, 100 points

| Weight | Check | What it means |
| ---: | --- | --- |
| 50 | Citation crawlers allowed | Split evenly across the six. Five of six allowed earns 41.67. |
| 20 | User fetch crawlers allowed | Split evenly across the five. |
| 15 | Sampled pages reachable | HTTP 200 and no sign of a login wall. |
| 10 | Sitemap declared and reachable | Declared in robots.txt and answering with XML. |
| 5 | No noindex | In the meta robots tag and in the `X-Robots-Tag` header. The header is the one people forget. |

### Critical failures that cap the score

All citation crawlers blocked caps Access at 20. A `User-agent: *` with
`Disallow: /` and nothing narrower caps it at 10, but only when it really shuts
everyone out. Files that block `*` and then name the crawlers they welcome are
common, and treating those as a total block would be wrong.

A homepage that does not answer 200 aborts the run and returns an error instead
of a score. There is nothing honest to score when the front door does not open.

## Readability, 100 points

| Weight | Check | What it means |
| ---: | --- | --- |
| 30 | Content in raw HTML | Measured, not rendered. See the limits below. |
| 20 | Valid JSON-LD | With a recognised schema.org type. Blocks that are not valid JSON are counted and reported, because they are invisible in a browser. |
| 15 | Heading structure | One h1, worth 0.6, and no skipped levels, worth 0.4. |
| 10 | Title and meta description | Present, 0.5 and 0.3, and unique across the sample, 0.2. |
| 10 | Author and dates | Half each. Read from meta tags, JSON-LD or a `time` element. |
| 5 | Canonical | Present and on the site's own host. |
| 5 | llms.txt | Present with real content. A proposal, not a standard, which is why it is 5 and not more. |
| 5 | Answer shaped content | Six extractable shapes, worth 0.6, and how well the prose is sectioned, worth 0.4. |

There are no caps on Readability. Every critical failure in this rubric is about
reachability, and a readable page nobody can fetch is already capped on the other
score.

## The heuristics, and what they can be wrong about

### The JavaScript check, 30 points

It does not render anything. It measures how much readable text arrives in the
initial HTML response and how much of that response is script.

The thresholds came from measurement. `scripts/calibrate_js_threshold.py`
sampled 22 live pages into `data/js_calibration.csv`, and two cuts came out of it:

Text below 500 characters. Three of the four known client rendered pages measured
32, 86 and 427 characters. Nothing server rendered came in below 1463.

A script to text ratio above 100. This caught two news homepages at
244 and 335, both of which ship almost no text and load the articles afterwards.
Every genuinely server rendered page in the sample sat below 35.

The fourth client rendered page is the one to know about. `jsonformatter.org`
renders in the browser and neither cut catches it: it ships 7773 characters of
static text around the app, and its script to text ratio is 0.27. The check
scores it as server rendered and is wrong about it. That is the shape of this
heuristic's failure, a client rendered page wrapped in enough real prose to look
like a document, and it is stated here rather than left for someone to find.

An empty mount point, a `div` with id `root` or `app` and nothing inside it, was
tested as a third signal and dropped. It found nothing the text rule had not
already found, and it would misfire on a server rendered page that mounts a
widget into an empty container.

It will mark down a page that is legitimately short. It will pass a page that
hides its content behind an interaction.

### Answer shaped content, 5 points

Two questions, weighted 0.6 and 0.4.

**Are there extractable shapes.** Six of them: numbered steps, a comparison
table, a question and answer block, a definition list, an attributed quote, a
summary box. Three anywhere in the sample earns that share in full.

**Is the prose in liftable pieces.** Measured as how much of a page escapes its
single largest block, where blocks are the text between headings. A page holding
one undivided wall scores nothing here; a page of evenly sized sections scores
full. A page too short to have sections is not penalised, because shortness is
what `raw_html_content` is for.

The idea for the second half comes from
[zubair-trabzada/geo-seo-claude](https://github.com/zubair-trabzada/geo-seo-claude),
MIT. The thresholds do not. That project scores blocks against an optimal band of
134 to 167 words, and its own documentation says its weights are editorial
judgements rather than empirically derived. Measuring 12301 blocks across 868
pages of this corpus showed why the band cannot be reused: the median real block
is 20 words, and 134 to 167 covers 2.6 percent of what exists. Scoring against it
would fail nearly every site without telling any of them apart.

What does separate is the largest block's share of the page. Across the 776 pages
with real prose the median is 0.40, a quarter sit at or below 0.24, and 13 percent
are effectively one wall. So at or below 0.35 earns full marks, at or above 0.80
earns nothing, and the space between is linear. The numbers are in
`data/block_calibration.csv`.

The check reads markup. It can see that a page has an ordered list of five steps
and that the prose is broken into sections. It cannot see whether either is any
good. It is worth five points because that is what a structural signal is worth.

### The login wall test, part of the 15 points

A 401 or 403, an authentication path in the final URL after redirects, or a
password field on a page with less than 1500 characters of visible text. A
paywall that serves the full article to the crawler and hides it with CSS passes
here, correctly, because the crawler does get the text.

## Two known weaknesses, stated rather than hidden

**The user fetch bucket counts blocks that do not work.** Three of the five
agents in it are documented by their own vendors as ignoring robots.txt:
`Perplexity-User` and `ChatGPT-User` explicitly, and `Meta-ExternalFetcher` for
user initiated requests. A `Disallow` aimed at them changes nothing, so a site
loses points here for a block that has no effect. The evidence line says exactly
which blocks are real, and the robots.txt fix leaves the ineffective ones out,
but the score still counts all five. Scoring only the agents that honour
robots.txt would give a truer number.

**The 20 point cap has never fired.** It requires every citation crawler to be
blocked, `Googlebot` included, and blocking Googlebot means leaving classic
search as well. Almost nobody does that. Across 906 real sites, exactly two shut
out every citation crawler, `reddit.com` and `create.it`, and both did it with a
blanket `User-agent: * / Disallow: /`, so both were caught by the stricter 10
point cap before this one could apply. The 20 point cap exists for a site that
names and blocks all six deliberately, and no site in the corpus does.

The failure that actually happens is narrower and nine times as common: every
crawler that exists only to feed AI answers blocked, while Google and Bing still
get through. Eighteen sites, against two. That is reported at full severity in the
evidence, and it does not change the score, because the rubric splits the 50
points evenly and changing that is a separate decision.

## What is deliberately not measured

Blocking at the CDN or WAF level. Real JavaScript rendering. Whether AI
assistants actually cite you. Batch mode across many domains. History and run
comparison.

The first of those is the largest gap. Across the corpus, 100 sites
returned HTTP 403 from a bot manager, and they return 403 to a browser user agent
just as readily. Their robots.txt is beside the point. This tool can only report
that the front door did not open, and it says so.
