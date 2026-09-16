#!/usr/bin/env python3
"""Cancel a pending Voice session or remove expired session metadata."""

from __future__ import annotations

import argparse
import json
import re

from vocab_runtime import (
    AnkiConnect,
    AnkiError,
    DEFAULT_URL,
    EXPECTED_FIELDS,
    MODEL,
    SchemaError,
    parse_state,
    voice_session_active,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cancel-session")
    group.add_argument("--expire-stale", action="store_true")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--authorized-voice-session-management", action="store_true")
    args = parser.parse_args()

    if not args.authorized_voice_session_management:
        print(json.dumps({"error": "refusing write without --authorized-voice-session-management"}))
        return 2
    if args.cancel_session and not re.fullmatch(r"voice-\d{4}-\d{2}-\d{2}-[a-f0-9]{8}", args.cancel_session):
        print(json.dumps({"error": "cancel-session has an unexpected format"}))
        return 2

    client = AnkiConnect(args.url, args.timeout)
    try:
        client.call("sync")
        fields = client.call("modelFieldNames", modelName=MODEL) or []
        if fields != EXPECTED_FIELDS:
            raise AnkiError("Vocabulary Sense fields differ from the activation-ledger schema")
        note_ids = client.call("findNotes", query='deck:"Vocabulary"') or []
        notes = client.call("notesInfo", notes=note_ids) if note_ids else []
        changed: list[int] = []
        removed: list[str] = []
        for note in notes:
            if note.get("modelName") != MODEL or not note.get("fields", {}).get("Activation State", {}).get("value"):
                continue
            state = parse_state(note)
            pending = [entry for entry in state.get("pending_voice_sessions", []) if isinstance(entry, dict)]
            kept: list[dict] = []
            for entry in pending:
                should_remove = (
                    entry.get("session_id") == args.cancel_session
                    if args.cancel_session
                    else not voice_session_active(entry)
                )
                if should_remove:
                    removed.append(str(entry.get("session_id")))
                else:
                    kept.append(entry)
            if len(kept) == len(pending):
                continue
            state["pending_voice_sessions"] = kept
            note_id = int(note["noteId"])
            client.call(
                "updateNoteFields",
                note={
                    "id": note_id,
                    "fields": {"Activation State": json.dumps(state, ensure_ascii=False, separators=(",", ":"))},
                },
            )
            changed.append(note_id)
        if changed:
            verified = client.call("notesInfo", notes=changed)
            for note in verified:
                state = parse_state(note)
                if args.cancel_session and any(
                    entry.get("session_id") == args.cancel_session
                    for entry in state.get("pending_voice_sessions", [])
                    if isinstance(entry, dict)
                ):
                    raise AnkiError("Voice-session cancellation verification failed")
        client.call("sync")
        print(
            json.dumps(
                {
                    "schema": "vocab-voice-session-management/v1",
                    "status": "updated" if changed else "noop",
                    "note_ids": changed,
                    "removed_session_ids": sorted(set(removed)),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (AnkiError, SchemaError) as error:
        print(json.dumps({"schema": "vocab-voice-session-management/v1", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
