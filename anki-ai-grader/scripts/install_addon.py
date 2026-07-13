#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


ADDON_NAME = "ai_grader"


def default_addons_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Anki2/addons21"
    if sys.platform.startswith("win"):
        return Path.home() / "AppData/Roaming/Anki2/addons21"
    return Path.home() / ".local/share/Anki2/addons21"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    source = repo_root / ADDON_NAME

    parser = argparse.ArgumentParser(
        description="Install the AI Typed Answer Grader into Anki's addons21 folder."
    )
    parser.add_argument(
        "--addons-dir",
        type=Path,
        default=default_addons_dir(),
        help="Path to Anki's addons21 folder.",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy files instead of creating a symlink.",
    )
    args = parser.parse_args()

    if not source.exists():
        raise SystemExit(f"Could not find add-on source folder: {source}")

    destination = args.addons_dir.expanduser() / ADDON_NAME
    args.addons_dir.mkdir(parents=True, exist_ok=True)

    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        else:
            shutil.rmtree(destination)

    if args.copy:
        shutil.copytree(source, destination)
        mode = "copied"
    else:
        destination.symlink_to(source, target_is_directory=True)
        mode = "symlinked"

    print(f"Installed {ADDON_NAME}: {mode}")
    print(f"Source: {source}")
    print(f"Destination: {destination}")
    print("Restart Anki, then set openai_api_key in Tools > Add-ons > AI Typed Answer Grader > Config.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
