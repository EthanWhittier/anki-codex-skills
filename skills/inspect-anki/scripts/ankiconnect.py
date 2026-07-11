#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import urllib.request
from typing import Any


URL = "http://127.0.0.1:8765"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: ankiconnect.py ACTION [PARAMS_JSON]", file=sys.stderr)
        return 2

    action = sys.argv[1]
    params: dict[str, Any] = {}
    if len(sys.argv) >= 3:
        try:
            params = json.loads(sys.argv[2])
        except json.JSONDecodeError as error:
            print(f"invalid PARAMS_JSON: {error}", file=sys.stderr)
            return 2

    payload = {"action": action, "version": 6}
    if params:
        payload["params"] = params

    request = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        print(f"failed to reach AnkiConnect at {URL}: {error}", file=sys.stderr)
        return 1

    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data.get("error") is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
