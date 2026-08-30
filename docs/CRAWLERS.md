# The crawler list

Every user agent `geo-check` knows about, what it does, and whether a
`Disallow` aimed at it actually stops anything.

This page is generated from
[src/geo_check/data/agents.json](../src/geo_check/data/agents.json), which is the
source of truth and ships inside the package. Last reviewed 2026-08-30:
every entry was checked against the vendor documentation linked in its row on
that date.

## Why the bucket matters more than the name

The score does not care what a crawler is called. It cares what blocking it
costs you, and that is what the bucket records.

**Citation crawlers**, worth 50 points of the Access score. Feeds retrieval and citation in AI answers.

**User fetch crawlers**, worth 20 points of the Access score. Fetches a page on demand when a user pastes a link or asks about it.

**Training crawlers**, worth nothing. Collects pages for model training.

Training is worth nothing on purpose. Blocking model training is a business
decision, and a tool that deducts points for it is arguing rather than
measuring. It appears as one informational line and moves neither score.

## When a block does nothing

Three of the on demand fetchers are documented by their own vendors as ignoring
`robots.txt`. A `Disallow` aimed at those changes nothing, so the report says so
instead of pretending the block worked, and they are left out of the robots.txt
block the tool offers you to paste. Only a server or WAF rule would stop them,
and this tool does not check that.

This is also the rubric's known weakness: those three still count toward the
user fetch score. Scoring only the agents that honour `robots.txt` would give a
truer number, and changing the rubric is the maintainer's call rather than a
silent fix. It is written up in [RUBRIC.md](RUBRIC.md).

## Citation crawlers

6 agents, worth 50 points.

| Agent | Vendor | Obeys robots.txt | What it does |
| --- | --- | --- | --- |
| `Applebot` | [Apple](https://support.apple.com/en-us/119829) | yes | Powers Spotlight, Siri and Safari search |
| `Bingbot` | [Microsoft](https://www.bing.com/webmasters/help/which-crawlers-does-bing-use-8c184ec0) | yes | Grounds Microsoft Copilot, and ChatGPT search also draws on the Bing index |
| `Claude-SearchBot` | [Anthropic](https://support.claude.com/en/articles/8896518) | yes | Improves search result quality for Claude users |
| `Googlebot` | [Google](https://developers.google.com/search/docs/crawling-indexing/google-common-crawlers) | yes | Feeds Google Search, and AI Overviews are built from that index |
| `OAI-SearchBot` | [OpenAI](https://developers.openai.com/api/docs/bots) | yes | Powers ChatGPT search |
| `PerplexityBot` | [Perplexity](https://docs.perplexity.ai/guides/bots) | yes | Surfaces and links websites in Perplexity results |

## User fetch crawlers

5 agents, worth 20 points.

| Agent | Vendor | Obeys robots.txt | What it does |
| --- | --- | --- | --- |
| `ChatGPT-User` | [OpenAI](https://developers.openai.com/api/docs/bots) | no | Fetches a page when a ChatGPT user asks about it |
| `Claude-User` | [Anthropic](https://support.claude.com/en/articles/8896518) | yes | Fetches a page when a Claude user asks about it |
| `Meta-ExternalFetcher` | [Meta](https://developers.facebook.com/docs/sharing/webmasters/web-crawlers) | no | Fetches individual links at a user's request |
| `MistralAI-User` | [Mistral](https://docs.mistral.ai/robots) | yes | On demand fetch for Le Chat |
| `Perplexity-User` | [Perplexity](https://docs.perplexity.ai/guides/bots) | no | Perplexity documents that this fetcher generally ignores robots.txt rules |

## Training crawlers

14 agents, worth zero points.

| Agent | Vendor | Obeys robots.txt | What it does |
| --- | --- | --- | --- |
| `Amazonbot` | [Amazon](https://developer.amazon.com/amazonbot) | yes | Improves Amazon products and trains Amazon AI models |
| `anthropic-ai` | [Anthropic](https://support.claude.com/en/articles/8896518) | yes | Legacy token, no longer listed in Anthropic documentation but still present in many robots.txt files |
| `Applebot-Extended` | [Apple](https://support.apple.com/en-us/119829) | yes | Opt out control for Apple foundation model training |
| `Bytespider` | [ByteDance](https://zhanzhang.toutiao.com/) | disputed | ByteDance claims robots.txt compliance but the reference URL is unreachable outside China, and independent measurements report it fetching disallowed pages |
| `CCBot` | [Common Crawl](https://commoncrawl.org/ccbot) | yes | Feeds an open crawl archive used by many downstream training datasets |
| `ClaudeBot` | [Anthropic](https://support.claude.com/en/articles/8896518) | yes |  |
| `cohere-ai` | [Cohere](https://cohere.com/) | yes | Collects web content for Cohere enterprise model training |
| `Diffbot` | [Diffbot](https://docs.diffbot.com/) | yes | Sells structured web data onward for AI training and retrieval, so one block covers many downstream consumers |
| `Google-Extended` | [Google](https://developers.google.com/search/docs/crawling-indexing/google-common-crawlers) | yes | Gemini training and grounding |
| `GPTBot` | [OpenAI](https://developers.openai.com/api/docs/bots) | yes | Training only |
| `meta-externalagent` | [Meta](https://developers.facebook.com/docs/sharing/webmasters/web-crawlers) | yes | Trains Meta foundation models and indexes content directly |
| `MistralAI-Training` | [Mistral](https://docs.mistral.ai/robots) | yes | Builds datasets for Mistral generative models |
| `omgilibot` | [Webz.io](https://webz.io/) | yes | Being replaced by webzio-extended |
| `webzio-extended` | [Webz.io](https://webz.io/) | yes | Successor token to omgilibot, specifically for AI training data |

## Correcting an entry

The list moves. Vendors rename crawlers, split them, and change their
documentation. A pull request that adds or corrects a row is the most useful
contribution to this project, and it needs one thing: the vendor's own
documentation URL in the `docs` field. Edit
[agents.json](../src/geo_check/data/agents.json) and regenerate this page.
