#!/usr/bin/env python3
"""Run Python code against an Anki Briefcase app's bundled modules."""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


resources = Path(os.environ["ANKI_APP_RESOURCES"])
app = str(resources / "app")
packages = str(resources / "app_packages")
sys.path[:0] = [app, packages]

# Briefcase splits Anki's package initializer and modules across two roots.
import anki

module_path = str(resources / "app_packages" / "anki")
if module_path not in anki.__path__:
    anki.__path__.append(module_path)

args = sys.argv[1:]
if not args:
    raise SystemExit("expected a script, -m module, or -c code")
if args[0] == "-m":
    if len(args) < 2:
        raise SystemExit("-m requires a module name")
    sys.argv = [args[1], *args[2:]]
    runpy.run_module(args[1], run_name="__main__", alter_sys=True)
elif args[0] == "-c":
    if len(args) < 2:
        raise SystemExit("-c requires code")
    sys.argv = ["-c", *args[2:]]
    exec(compile(args[1], "<string>", "exec"), {"__name__": "__main__"})
else:
    script = args[0]
    sys.argv = [script, *args[1:]]
    runpy.run_path(script, run_name="__main__")
