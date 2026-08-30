---
name: geo-check
description: Check whether a website is reachable and readable by AI crawlers, and score it. Use when the user asks whether their site is blocked from ChatGPT, Claude, Perplexity or Google AI Overviews, wants a robots.txt reviewed for AI bots, asks about GEO or AEO, llms.txt, or wants to know why their site is not being cited by AI assistants. Requires network access and Python 3.10 or newer.
---

# geo-check

Audits a domain for AI crawler access and AI readability, then reports two
scores with letter grades and concrete fixes, including the exact robots.txt
lines to paste.

## When to use this

The user asks any of: is my site blocked from ChatGPT, why am I not cited by AI,
review my robots.txt for AI bots, do I need llms.txt, is my site GEO or AEO
ready, why does Perplexity never mention us.

## Requirements

Network access and Python 3.10 or newer. This does not work inside restricted
sandboxes that only reach an allowlist of domains.

## How to run

```bash
pip install -e .
```

```bash
geo-check example.com
```

```bash
geo-check example.com --pages 10 --json report.json --output report.md
```

The JSON is the real result. The markdown report and the terminal output are
rendered from it.

## How to read the result

Two scores, never averaged. Report them separately and say why.

**Access** is whether AI systems can reach the site at all: robots.txt, HTTP
status, sitemap availability, noindex directives.

**Readability** is whether an AI system can make sense of a page once it has it:
content in the raw HTML, structured data, headings, metadata, attribution.

Crawlers fall into three buckets. Citation crawlers feed AI answers, and
blocking them removes the site from those answers. User fetch crawlers retrieve
one page when someone asks about a link. Training crawlers collect pages for
model training, are worth no points, and appear only as a posture line.

## Things to get right when reporting

**Never tell someone to unblock training crawlers to improve their score.** It
would not improve their score, because training is worth zero. Blocking training
is a business decision and saying otherwise is bad advice.

**The distinction that matters is `GPTBot` against `OAI-SearchBot`.** The first
is training and blocking it costs nothing in ChatGPT results. The second is
search and blocking it removes the site from them. Most people who think they
opted out of training have done exactly that and no more, which is fine, and
some have taken search down with it, which is usually not what they meant.

**Some blocks do not work and the report says which.** `Perplexity-User`,
`ChatGPT-User` and `Meta-ExternalFetcher` are documented by their own vendors as
ignoring robots.txt. Do not tell the user to change a rule aimed at those.

**A run that aborts is not a failure of the tool.** A 401, 403 or a 202
challenge on the homepage is a block above robots.txt, at the CDN or bot manager.
Report it as what it is, and do not claim it means the site blocks AI crawlers,
because some of those same sites allowlist AI crawlers at the edge.

## Limitations to state when reporting results

This reads robots.txt and page markup. It does not detect CDN or WAF level
blocking, so a site can pass every check and still return 403 to AI crawlers in
practice. The JavaScript check is a heuristic over text volume and script
weight, not real rendering. Answer shaped content is detected structurally, so
it sees that a list of steps exists and not whether the steps are useful.

The full rubric, including why training crawlers score zero, is in
`docs/RUBRIC.md`.
