#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def update(text: str, mcp_path: str) -> str:
    lines = text.splitlines()
    section = "[mcp_servers.anki-mcp]"
    desired = f'args = ["{mcp_path}"]'
    try:
        start = lines.index(section)
    except ValueError:
        if lines and lines[-1]:
            lines.append("")
        lines.extend([section, 'command = "node"', desired, ""])
        return "\n".join(lines)

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("["):
            end = index
            break
    for index in range(start + 1, end):
        if lines[index].startswith("args ="):
            lines[index] = desired
            break
    else:
        lines.insert(start + 1, desired)
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


parser = argparse.ArgumentParser()
parser.add_argument("config", type=Path)
parser.add_argument("mcp_path")
args = parser.parse_args()
args.config.write_text(update(args.config.read_text(), args.mcp_path))
