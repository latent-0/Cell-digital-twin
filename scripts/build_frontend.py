#!/usr/bin/env python3
"""Assemble the self-contained frontend from style.css + app.js + twindata.json.

Outputs:
  frontend/index.html   -- standalone, open directly in any browser (offline)
  <artifact_out>        -- body-only variant for the Claude Artifact (optional arg)
"""

from __future__ import annotations

import sys
from pathlib import Path

FE = Path(__file__).resolve().parents[1] / "frontend"


def main():
    css = (FE / "style.css").read_text()
    js = (FE / "app.js").read_text()
    data = (FE / "twindata.json").read_text()

    data_script = f"<script>window.TWIN_DATA={data};</script>"
    body = f'<div id="app"></div>\n{data_script}\n<script>{js}</script>'

    standalone = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Cell Digital Twin — Toxicology Screening</title>\n"
        f"<style>{css}</style>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )
    (FE / "index.html").write_text(standalone)
    print(f"Wrote {FE/'index.html'} ({len(standalone)//1024} KB)")

    if len(sys.argv) > 1:
        art = Path(sys.argv[1])
        art.write_text(f"<style>{css}</style>\n{body}\n")
        print(f"Wrote {art} ({art.stat().st_size//1024} KB)")


if __name__ == "__main__":
    main()
