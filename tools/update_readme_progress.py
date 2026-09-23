#!/usr/bin/env python3
"""Regenerate the README progress badge and table from PROGRESS.md.

PROGRESS.md is the single source of truth. Its header line
    **Game functions identified: 975 · named: 25 · verified: 0** ...
gives the counts. This script draws the bars and rewrites the marked regions in README.md
(<!-- PROGRESS:BADGE --> and <!-- PROGRESS:TABLE -->) so the two files never drift.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROGRESS = os.path.join(ROOT, "PROGRESS.md")
README = os.path.join(ROOT, "README.md")
BAR_SEGMENTS = 20


def bar(frac):
    n = round(frac * BAR_SEGMENTS)
    return "▰" * n + "▱" * (BAR_SEGMENTS - n)


def main():
    text = open(PROGRESS, encoding="utf-8").read()
    m = re.search(r"identified:\s*(\d+)\s*·\s*named:\s*(\d+)\s*·\s*verified:\s*(\d+)", text)
    if not m:
        sys.exit("progress line not found in PROGRESS.md")
    total, named, verified = map(int, m.groups())
    pn, pv = named / total, verified / total
    badge = (
        f"![named](https://img.shields.io/badge/named-{named}%2F{total}%20({pn*100:.2f}%25)-1f6feb)\n"
        f"![verified](https://img.shields.io/badge/verified-{verified}%2F{total}%20({pv*100:.2f}%25)-2ea043)"
    )
    table = (
        "| Metric | Functions | Count | Progress |\n"
        "|---|---:|---:|---|\n"
        f"| **Named** (symbol + evidence) | {total} | {named} | `{bar(pn)}` {pn*100:.2f}% |\n"
        f"| **Verified** (recon passes trace diff) | {total} | {verified} | `{bar(pv)}` {pv*100:.2f}% |"
    )
    readme = open(README, encoding="utf-8").read()
    for tag, body in (("BADGE", badge), ("TABLE", table)):
        readme, k = re.subn(rf"(<!-- PROGRESS:{tag} -->\n).*?(<!-- /PROGRESS:{tag} -->)",
                            lambda mm: mm.group(1) + body + "\n" + mm.group(2), readme, flags=re.S)
        if k != 1:
            sys.exit(f"README marker PROGRESS:{tag} missing")
    open(README, "w", encoding="utf-8", newline="\n").write(readme)
    print(f"named {named}/{total}, verified {verified}/{total}")


if __name__ == "__main__":
    main()
