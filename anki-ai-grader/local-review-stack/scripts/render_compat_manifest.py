#!/usr/bin/env python3
"""Render the add-on compatibility manifest from versions.env."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"').strip("'")
    return values


root = Path(__file__).resolve().parents[1]
values = read_env(root / "versions.env")
versions = [item.strip() for item in values.get("TESTED_ANKI_VERSIONS", "").split(",") if item.strip()]
if not versions:
    raise SystemExit("TESTED_ANKI_VERSIONS must contain at least one exact Anki version")

target = root / "anki-connect" / "plugin" / "chat_review_compat.json"
rendered = json.dumps({"testedAnkiVersions": versions}, indent=2) + "\n"
if "--check" in sys.argv:
    if not target.exists() or target.read_text(encoding="utf-8") != rendered:
        raise SystemExit(f"{target} is stale; run scripts/build.sh after updating versions.env")
else:
    target.write_text(rendered, encoding="utf-8")
