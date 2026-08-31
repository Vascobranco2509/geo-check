"""Markdown report, rendered from the JSON payload and never from raw results.

Written for someone who has never seen this tool. It opens with what to change,
because that is the only part most readers act on, and it states its own limits
before anyone has to discover them.
"""

from __future__ import annotations

FENCE = "```"

SEVERITY_LABEL = {
    "ok": "OK",
    "info": "Note",
    "warning": "Warning",
    "critical": "CRITICAL",
}

CATEGORY_TITLE = {"access": "Access", "readability": "Readability"}

BUCKET_HEADING = {
    "citation": "Citation crawlers",
    "user_fetch": "User fetch crawlers",
    "training": "Training crawlers",
}

CATEGORY_BLURB = {
    "access": (
        "Whether AI systems can reach the site at all. Driven by robots.txt, HTTP"
        " status, sitemap availability and noindex directives."
    ),
    "readability": (
        "Whether an AI system can make sense of a page once it has it. Driven by"
        " content in the raw HTML, structured data, headings, metadata and"
        " attribution."
    ),
}

WHY_NOT_AVERAGED = (
    "The two scores are never averaged. A site can be wide open and unreadable,"
    " and the average would hide exactly the problem worth seeing."
)

TRAINING_BLURB = (
    "Blocking model training is a legitimate business decision, not a mistake."
    " It costs no points here and appears only as a posture line."
)


def escape_cell(value: str) -> str:
    """A pipe inside a table cell has to be escaped or it splits the column."""
    return value.replace("|", r"\|")


def fence(body: str, language: str = "") -> str:
    return FENCE + language + "\n" + body.rstrip("\n") + "\n" + FENCE


def _header(payload: dict) -> list[str]:
    run = payload["run"]
    tool = payload["tool"]
    return [
        "# geo-check report: " + run["domain"],
        "",
        "  \n".join(
            [
                run["base_url"],
                str(run["pages_sampled"]) + " pages sampled",
                "generated " + run["generated_at"],
                tool["name"] + " " + tool["version"],
            ]
        ),
        "",
    ]


def _scores(payload: dict) -> list[str]:
    scores = payload["scores"]
    lines = [
        "| Score | Result | Grade |",
        "| --- | --- | --- |",
    ]
    for key in ("access", "readability"):
        entry = scores[key]
        lines.append(
            "| **"
            + CATEGORY_TITLE[key]
            + "** | "
            + format(entry["score"], "g")
            + " / 100 | "
            + entry["letter"]
            + " |"
        )
    lines += ["", WHY_NOT_AVERAGED, ""]

    for key in ("access", "readability"):
        cap = scores[key]["cap_applied"]
        if cap:
            lines += [
                "> **CRITICAL** "
                + CATEGORY_TITLE[key]
                + " is capped at "
                + format(scores[key]["score"], "g")
                + ": "
                + cap
                + ".",
                "",
            ]

    signals = payload.get("content_signals")
    if signals:
        lines += ["**Content signals.** " + signals["summary"], ""]
        if signals["unknown_keys"]:
            lines += [
                "Keys we do not recognise, which may simply be newer than this tool: "
                + ", ".join("`" + k + "`" for k in signals["unknown_keys"]),
                "",
            ]

    posture = payload["training_posture"]
    lines += [
        "**Training posture: "
        + posture["state"]
        + "** ("
        + str(posture["allowed"])
        + " of "
        + str(posture["total"])
        + " training crawlers allowed). "
        + TRAINING_BLURB,
        "",
    ]
    return lines


def _actions(payload: dict) -> list[str]:
    """The part most readers act on, so it goes first."""
    failed = [c for c in payload["checks"] if c["fix"] and c["ratio"] < 1.0]
    if not failed:
        return ["## What to change", "", "Nothing. Every check passed.", ""]

    lines = ["## What to change first", ""]
    additions = payload.get("robots_txt_additions", "")
    if additions:
        lines += [
            "Add these lines to `" + payload["robots"]["url"] + "`. They sit alongside"
            " whatever rules are already there, and none of them opens the site to"
            " model training.",
            "",
            fence(additions, "text"),
            "",
        ]

    ordered = sorted(failed, key=lambda c: c["weight"] * (1 - c["ratio"]), reverse=True)
    lines += ["The changes worth the most points, heaviest first:", ""]
    for check in ordered[:5]:
        cost = round(check["weight"] * (1 - check["ratio"]), 1)
        lines.append(
            "- **"
            + check["title"]
            + "** ("
            + format(cost, "g")
            + " points): "
            + check["fix"]["summary"]
        )
    lines.append("")
    return lines


def _category(payload: dict, category: str) -> list[str]:
    entry = payload["scores"][category]
    checks = [c for c in payload["checks"] if c["category"] == category]

    lines = [
        "## "
        + CATEGORY_TITLE[category]
        + ", "
        + format(entry["score"], "g")
        + " / 100 ("
        + entry["letter"]
        + ")",
        "",
        CATEGORY_BLURB[category],
        "",
        "| Check | Earned | Weight | |",
        "| --- | ---: | ---: | --- |",
    ]
    for check in checks:
        lines.append(
            "| "
            + check["title"]
            + " | "
            + format(check["earned"], "g")
            + " | "
            + str(check["weight"])
            + " | "
            + SEVERITY_LABEL.get(check["severity"], check["severity"])
            + " |"
        )
    lines.append("")

    for check in checks:
        lines += [
            "### " + check["title"],
            "",
            format(check["earned"], "g")
            + " of "
            + str(check["weight"])
            + " points. "
            + SEVERITY_LABEL.get(check["severity"], check["severity"])
            + ".",
            "",
            check["evidence"],
            "",
        ]
        fix = check["fix"]
        if fix:
            lines += ["**Fix.** " + fix["summary"], ""]
            if fix["snippet"]:
                lines += [fence(fix["snippet"], "text"), ""]
            if fix["docs_url"]:
                lines += ["Reference: <" + fix["docs_url"] + ">", ""]
    return lines


def _crawlers(payload: dict) -> list[str]:
    lines = [
        "## Crawlers",
        "",
        (
            "Citation crawlers feed AI answers, and blocking them removes the site"
            " from those answers. User fetch crawlers retrieve one page when someone"
            " asks about a link. Training crawlers collect pages for model training"
            " and are worth no points here."
        ),
        "",
    ]
    for bucket, heading in BUCKET_HEADING.items():
        data = payload["crawlers"][bucket]
        lines += [
            "### "
            + heading
            + ", "
            + str(data["allowed"])
            + " of "
            + str(data["total"])
            + " allowed",
            "",
            "| Agent | Vendor | Verdict | Rule that decided it |",
            "| --- | --- | --- | --- |",
        ]
        for agent in data["agents"]:
            verdict = "allowed" if agent["allowed"] else "blocked"
            if not agent["allowed"] and agent["obeys_robots"] != "yes":
                verdict += " (ignores robots.txt)"
            rule = agent["matched_rule"] or "no rule mentions it, so it is allowed"
            lines.append(
                "| `"
                + agent["token"]
                + "` | "
                + agent["vendor"]
                + " | "
                + verdict
                + " | `"
                + escape_cell(rule)
                + "` |"
            )
        lines.append("")
    return lines


def _notes(payload: dict) -> list[str]:
    robots = payload["robots"]
    sitemap = payload["sitemap"]
    lines = ["## How this was measured", ""]

    if robots["is_real"]:
        lines.append(
            "- robots.txt read from " + robots["url"] + " (HTTP " + str(robots["status"]) + ")"
        )
    elif robots["status"] == 200:
        lines.append(
            "- " + robots["url"] + " answered 200 with something that is not robots"
            " syntax, usually a homepage. Treated as absent, so everything is allowed"
        )
    else:
        lines.append(
            "- No robots.txt (HTTP "
            + str(robots["status"])
            + "). Everything is allowed by default, which is full marks on that"
            " dimension and not a problem"
        )

    lines.append("- Sitemap declared: " + (sitemap["declared"] or "none"))
    lines.append("- Sitemap read: " + (sitemap["reachable"] or "none"))
    lines.append("- Pages sampled, chosen deterministically so two runs match:")
    for page in payload["pages"]:
        lines.append("    - " + str(page["status"]) + " " + page["url"])
    for error in payload["errors"]:
        lines.append("- " + error)
    lines.append("")

    lines += ["## What this does not do", ""]
    lines += ["- " + limitation for limitation in payload["limitations"]]
    lines.append("")
    return lines


def render(payload: dict) -> str:
    """The whole report, from the payload and nothing else."""
    blocks = (
        _header(payload)
        + _scores(payload)
        + _actions(payload)
        + _category(payload, "access")
        + _category(payload, "readability")
        + _crawlers(payload)
        + _notes(payload)
    )
    return "\n".join(blocks).rstrip() + "\n"
