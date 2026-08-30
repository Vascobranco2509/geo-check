"""Measure raw HTML text volume across real sites, to set the JavaScript threshold.

The raw_html_content check is worth 30 points, the heaviest in the Readability
rubric, and it rests on a threshold. Picking a round number and calling it a
heuristic would be guessing with extra steps. This script produces the numbers
the threshold is chosen from, and it is kept in the repository so anyone can
disagree with the choice using the same evidence.

Run it deliberately. It hits live sites, and it needs the package installed.

    python scripts/calibrate_js_threshold.py
"""

from __future__ import annotations

import csv
from pathlib import Path

from geo_check.fetch import fetch, new_client
from geo_check.models import PageContext

# Sites expected to serve their content in the initial HTML response.
SERVER_RENDERED = [
    "https://observador.pt/",
    "https://sapo.pt/",
    "https://www.jn.pt/",
    "https://www.dn.pt/",
    "https://www.noticiasaominuto.com/",
    "https://www.cmjornal.pt/",
    "https://eco.sapo.pt/",
    "https://www.record.pt/",
    "https://www.fnac.pt/",
    "https://www.continente.pt/",
    "https://www.radiopopular.pt/",
    "https://www.outsystems.com/",
    "https://unbabel.com/",
    "https://www.talkdesk.com/",
    "https://feedzai.com/",
    "https://remote.com/",
    "https://en.wikipedia.org/wiki/Portugal",
    "https://stackoverflow.com/questions",
    "https://www.bbc.com/news",
    "https://news.ycombinator.com/",
]

# Sites expected to render their content in the browser, after the HTML arrives.
CLIENT_RENDERED = [
    "https://demo.realworld.io/",
    "https://todomvc.com/examples/react/dist/",
    "https://app.diagrams.net/",
    "https://excalidraw.com/",
    "https://jsonformatter.org/",
]

SHELL_IDS = ("root", "app", "__next", "__nuxt", "main-app", "svelte")


def script_chars(page: PageContext) -> int:
    return sum(len(tag.get_text() or "") for tag in page.soup.find_all("script"))


def looks_like_a_shell(page: PageContext) -> bool:
    """An empty mount point with nothing in it is the signature of client rendering."""
    for element in page.soup.find_all(["div", "main", "section"], id=True):
        if element.get("id", "").lower() in SHELL_IDS and len(element.get_text(strip=True)) < 50:
            return True
    return False


def measure(url: str, client, expected: str) -> dict | None:
    result = fetch(url, client)
    if not result.ok:
        print(f"  skipped {url}: HTTP {result.status} {result.error or ''}".rstrip())
        return None
    page = PageContext(
        url=result.final_url, status=result.status, headers=result.headers, html=result.text
    )
    text = len(page.text)
    html = len(page.html) or 1
    scripts = script_chars(page)
    return {
        "url": result.final_url,
        "expected": expected,
        "text_chars": text,
        "html_chars": html,
        "script_chars": scripts,
        "text_over_html": round(text / html, 4),
        "script_over_text": round(scripts / text, 2) if text else 9999,
        "shell": looks_like_a_shell(page),
    }


def main() -> int:
    client = new_client()
    rows = []
    try:
        for group, urls in (("server", SERVER_RENDERED), ("client", CLIENT_RENDERED)):
            print(f"--- {group} rendered ---")
            for url in urls:
                row = measure(url, client, group)
                if row:
                    rows.append(row)
                    print(
                        f"  {row['text_chars']:>7} chars  "
                        f"text/html {row['text_over_html']:.3f}  "
                        f"script/text {row['script_over_text']:>8}  "
                        f"shell={row['shell']!s:5}  {url}"
                    )
    finally:
        client.close()

    out = Path(__file__).resolve().parents[1] / "data" / "js_calibration.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n{len(rows)} pages measured, written to {out}")

    for group in ("server", "client"):
        values = sorted(r["text_chars"] for r in rows if r["expected"] == group)
        if values:
            print(
                f"{group:7} text_chars  min={values[0]}  median={values[len(values) // 2]}  max={values[-1]}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
