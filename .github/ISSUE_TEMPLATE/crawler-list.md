---
name: Crawler list correction
about: An agent is missing, in the wrong bucket, or its documentation moved
title: "agents.json: "
labels: crawler-list
---

The most useful contribution to this project. The bucket an agent sits in is
what the whole Access score rests on, and vendors rename and reclassify
crawlers without announcing it.

**Agent token**


**What is wrong**

Missing, wrong bucket, wrong `obeys_robots`, dead documentation URL, or renamed.

**Vendor documentation URL**

Required. A page the vendor publishes, not a third party crawler directory.
Entries in `src/geo_check/data/agents.json` are only accepted with one, because
the file records what vendors say rather than what the field believes.

**Which bucket, and why**

- `citation` feeds retrieval and citation in AI answers
- `user_fetch` retrieves one page on demand when someone asks about a link
- `training` collects pages for model training, and is worth no points

**Anything the vendor says about robots.txt**

Some fetchers are documented as ignoring it. If this one is, quote the line.
