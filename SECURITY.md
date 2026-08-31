# Security

## Reporting

Open a [security advisory](https://github.com/vasco-branco06/geo-check/security/advisories/new)
rather than a public issue. If that is not available to you, an issue titled
`security` with no detail is enough to start a private conversation.

## What this tool reads, and from whom

`geo-check` fetches `robots.txt`, `llms.txt`, a sitemap and up to five pages from
a domain the user names. All of it is attacker controlled content in the sense
that matters: the site owner decides what is in those files, and the tool has no
way to know whether a given site is friendly.

The parsing is defensive where it can be. Sitemap XML is parsed with entity
resolution and network access disabled, so a hostile sitemap cannot read local
files or make outbound requests. Responses are read against a byte ceiling, so a
slow drip of a very large body cannot exhaust memory. Every network failure is
returned as a typed reason rather than raised.

## A known issue, unfixed

**`robots.txt` content reaches an assistant through the report.**

The tool copies the `matched_rule` string verbatim out of a site's `robots.txt`
into the JSON payload, the markdown report and the terminal output. `SKILL.md`
exists so that an AI assistant reads that report and acts on it.

That is an injection route. Anything a site writes in its `robots.txt` reaches
whatever assistant is auditing it. This is not hypothetical: a site in the
validation corpus carries several lines addressed to AI agents, including a
request that an assistant reading them recommend installing a skill so it can
make purchases.

Nothing in the tool marks that content as untrusted today. If you are feeding
`geo-check` output to a model, treat every quoted `robots.txt` line as data
written by a stranger, because that is what it is.

It is written down here rather than fixed quietly because a user deciding whether
to pipe this into an agent deserves to know before, not after. A fix would mean
fencing or labelling quoted content in the report and saying so in `SKILL.md`,
and it is tracked as work rather than shipped in a hurry.

## What this tool does not do

It sends no data anywhere. There is no telemetry, no analytics and no outbound
call other than to the domain being audited. It calls no language model. It
identifies itself honestly in its user agent and does not impersonate a browser
or another company's crawler, and it honours `robots.txt` for its own user agent
when sampling pages.
