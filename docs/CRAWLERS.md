# The crawler list

Every user agent `geo-check` knows about, what it does, and whether a
`Disallow` aimed at it actually stops anything.

This page is generated from
[src/geo_check/data/agents.json](../src/geo_check/data/agents.json), which is the
source of truth and ships inside the package. Last reviewed 2026-09-05:
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

6 of the 8 on demand fetchers are documented by their own vendors as not
honouring `robots.txt`. A `Disallow` aimed at those changes nothing, so the report says so
instead of pretending the block worked, and they are left out of the robots.txt
block the tool offers you to paste. Only a server or WAF rule would stop them,
and this tool does not check that.

They also no longer cost anything. Until 0.2.0 they counted toward the user
fetch score, so a site lost points for a block that did not work; [RUBRIC.md](RUBRIC.md)
had said in writing that this was wrong, and now only an effective block costs
points. The counts above still report what the `robots.txt` says, which is a
different question from what it achieves.

## Citation crawlers

11 agents, worth 50 points.

| Agent | Vendor | Obeys robots.txt | What it does |
| --- | --- | --- | --- |
| `Amzn-SearchBot` | [Amazon](https://developer.amazon.com/amazonbot) | yes | Makes content eligible for Alexa search experiences, and Amazon documents that it does not crawl for generative AI training |
| `Applebot` | [Apple](https://support.apple.com/en-us/119829) | yes | Powers Spotlight, Siri and Safari search |
| `Bingbot` | [Microsoft](https://www.bing.com/webmasters/help/which-crawlers-does-bing-use-8c184ec0) | yes | Grounds Microsoft Copilot, and ChatGPT search also draws on the Bing index |
| `Claude-SearchBot` | [Anthropic](https://support.claude.com/en/articles/8896518) | yes | Improves search result quality for Claude users |
| `DuckAssistBot` | [DuckDuckGo](https://duckduckgo.com/duckduckgo-help-pages/results/duckassistbot/) | yes | Feeds DuckDuckGo's AI assisted answers, which cite their sources, and the data is not used for training |
| `Googlebot` | [Google](https://developers.google.com/search/docs/crawling-indexing/google-common-crawlers) | yes | Feeds Google Search, and AI Overviews are built from that index |
| `Meta-WebIndexer` | [Meta](https://developers.facebook.com/docs/sharing/webmasters/web-crawlers) | yes | Meta's own page says allowing this one helps Meta AI cite and link to your content |
| `MistralAI-Index` | [Mistral](https://docs.mistral.ai/robots) | yes | Indexes for Mistral search, which answers questions in Vibe |
| `OAI-SearchBot` | [OpenAI](https://developers.openai.com/api/docs/bots) | yes | Powers ChatGPT search |
| `PerplexityBot` | [Perplexity](https://docs.perplexity.ai/guides/bots) | yes | Surfaces and links websites in Perplexity results |
| `YouBot` | [You.com](https://you.com/docs/youbot) | yes | Powers the You.com search engine, which is an AI answer product rather than a classic index, so blocking it costs nothing in Google or Bing |

## User fetch crawlers

8 agents, worth 20 points.

| Agent | Vendor | Obeys robots.txt | What it does |
| --- | --- | --- | --- |
| `Amzn-User` | [Amazon](https://developer.amazon.com/amazonbot) | no | Answers Alexa queries that need current information |
| `ChatGPT-User` | [OpenAI](https://developers.openai.com/api/docs/bots) | disputed | Fetches a page when someone asks ChatGPT about a link |
| `Claude-User` | [Anthropic](https://support.claude.com/en/articles/8896518) | yes | Fetches a page when a Claude user asks about it |
| `Google-Agent` | [Google](https://developers.google.com/search/docs/crawling-indexing/google-user-triggered-fetchers) | no | Web navigation on behalf of Google infrastructure agents, user triggered and therefore documented as generally ignoring robots.txt |
| `Google-GeminiNotebook` | [Google](https://developers.google.com/search/docs/crawling-indexing/google-user-triggered-fetchers) | no | Fetches a page a person added to Gemini Notebook |
| `Meta-ExternalFetcher` | [Meta](https://developers.facebook.com/docs/sharing/webmasters/web-crawlers) | no | Fetches individual links at a user's request |
| `MistralAI-User` | [Mistral](https://docs.mistral.ai/robots) | yes | On demand fetch for Vibe, formerly named Le Chat |
| `Perplexity-User` | [Perplexity](https://docs.perplexity.ai/guides/bots) | no | Perplexity documents that this fetcher generally ignores robots.txt rules |

## Training crawlers

13 agents, worth zero points.

| Agent | Vendor | Obeys robots.txt | What it does |
| --- | --- | --- | --- |
| `Amazonbot` | [Amazon](https://developer.amazon.com/amazonbot) | yes | Improves Amazon products and trains Amazon AI models |
| `anthropic-ai` | [Anthropic](https://support.claude.com/en/articles/8896518) | yes | A legacy token |
| `Applebot-Extended` | [Apple](https://support.apple.com/en-us/119829) | yes | Opt out control for Apple foundation model training |
| `Bytespider` | ByteDance | disputed | ByteDance publishes no crawler page, no IP list and no robots.txt statement in any reachable form |
| `CCBot` | [Common Crawl](https://commoncrawl.org/ccbot) | yes | Feeds an open crawl archive used by many downstream training datasets |
| `ClaudeBot` | [Anthropic](https://support.claude.com/en/articles/8896518) | yes | Anthropic's training crawler |
| `Diffbot` | [Diffbot](https://www.diffbot.com/docs/crawl/faq/robots-txt) | disputed | Diffbot documents that its crawls adhere to robots.txt by default, including Disallow and Crawl-delay, but that the instruction can be overridden under a partnership or agreement |
| `Google-Extended` | [Google](https://developers.google.com/search/docs/crawling-indexing/google-common-crawlers) | yes | Gemini training and grounding |
| `GPTBot` | [OpenAI](https://developers.openai.com/api/docs/bots) | yes | Training only |
| `meta-externalagent` | [Meta](https://developers.facebook.com/docs/sharing/webmasters/web-crawlers) | yes | Trains Meta foundation models and indexes content directly |
| `MistralAI-Training` | [Mistral](https://docs.mistral.ai/robots) | yes | Builds datasets for Mistral generative models |
| `omgilibot` | [Webz.io](https://webz.io/) | yes | Webz.io describes this one as replaced by its Webzio pair |
| `webzio-extended` | [Webz.io](https://webz.io/) | yes | Successor token to omgilibot, specifically for AI training data |

## Correcting an entry

The list moves. Vendors rename crawlers, split them, and change their
documentation. A pull request that adds or corrects a row is the most useful
contribution to this project, and it needs one thing: the vendor's own
documentation URL in the `docs` field. Edit
[agents.json](../src/geo_check/data/agents.json) and regenerate this page.
