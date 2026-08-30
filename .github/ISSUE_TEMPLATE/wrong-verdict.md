---
name: Wrong verdict
about: The tool says a crawler is blocked or allowed and it is not
title: "wrong verdict: "
labels: bug
---

**Domain**


**What the tool said**

Paste the relevant lines, including the `because of` line, which names the
robots.txt group that produced the verdict.

```
```

**What you believe is correct, and why**


**The robots.txt**

Paste the groups that mention the agent, with a few lines either side. Context
matters more than it looks: three defects found so far came from a directive
between groups, a group declared twice, and a group whose name was a substring
of the agent token.

```
```

**Version**

`geo-check --help` prints it, or give the commit.

---

Verdicts are decided in `src/geo_check/robots.py` and every one of the three
known defects was reported this way. A report with the robots.txt attached can
be turned into a regression test the same day; one without it usually cannot be
reproduced at all.
