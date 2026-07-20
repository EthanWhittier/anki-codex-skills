#!/usr/bin/env python3
"""Migrate Vocabulary Sense to the activation-ledger fields and initialize active notes."""

from __future__ import annotations

import argparse
import json
from datetime import date

from vocab_runtime import (
    AnkiConnect,
    AnkiError,
    DEFAULT_URL,
    EXPECTED_FIELDS,
    MODEL,
    cohort_start_from_tags,
    field,
    initial_ledger,
    initial_state,
    normalize_goals,
)


LEGACY_FIELDS = EXPECTED_FIELDS[:-2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sense-goals-json", default="{}", help="Map Sense ID to speech/writing goal lists.")
    parser.add_argument("--default-goals", default="writing")
    parser.add_argument("--enable-voice", action="store_true")
    parser.add_argument("--authorize-evidence-recording", action="store_true")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--authorized-schema-migration", action="store_true")
    args = parser.parse_args()

    if not args.authorized_schema_migration:
        print(json.dumps({"error": "refusing write without --authorized-schema-migration"}))
        return 2
    try:
        goal_map = json.loads(args.sense_goals_json)
        if not isinstance(goal_map, dict):
            raise ValueError("sense-goals-json must be an object")
        default_goals = normalize_goals([value.strip() for value in args.default_goals.split(",")])
    except (json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"error": str(error)}))
        return 2

    client = AnkiConnect(args.url, args.timeout)
    try:
        client.call("sync")
        fields = client.call("modelFieldNames", modelName=MODEL) or []
        schema_changed = False
        if fields == LEGACY_FIELDS:
            client.call("modelFieldAdd", modelName=MODEL, fieldName="Activation State")
            client.call("modelFieldAdd", modelName=MODEL, fieldName="Activation Evidence")
            schema_changed = True
        elif fields != EXPECTED_FIELDS:
            raise AnkiError(f"unexpected {MODEL} fields; no migration attempted")
        verified_fields = client.call("modelFieldNames", modelName=MODEL) or []
        if verified_fields != EXPECTED_FIELDS:
            raise AnkiError("field migration verification failed")

        note_ids = client.call("findNotes", query='deck:"Vocabulary" tag:vocab::stage::activation') or []
        notes = client.call("notesInfo", notes=note_ids) if note_ids else []
        initialized: list[int] = []
        for note in notes:
            if note.get("modelName") != MODEL:
                continue
            sense_id = field(note, "Sense ID")
            has_state = bool(field(note, "Activation State"))
            has_ledger = bool(field(note, "Activation Evidence"))
            if has_state and has_ledger:
                continue
            if has_state != has_ledger:
                raise AnkiError(f"active note {note['noteId']} has only one activation field populated; refusing overwrite")
            goals = normalize_goals(goal_map.get(sense_id, default_goals))
            started = cohort_start_from_tags(list(note.get("tags", []))) or date.today()
            state = initial_state(
                sense_id,
                started,
                goals=goals,
                recording_authorized=args.authorize_evidence_recording,
                voice_enabled=args.enable_voice and "speech" in goals,
            )
            ledger = initial_ledger(sense_id)
            client.call(
                "updateNoteFields",
                note={
                    "id": int(note["noteId"]),
                    "fields": {
                        "Activation State": json.dumps(state, ensure_ascii=False, separators=(",", ":")),
                        "Activation Evidence": json.dumps(ledger, ensure_ascii=False, separators=(",", ":")),
                    },
                },
            )
            initialized.append(int(note["noteId"]))

        if initialized:
            verified_notes = client.call("notesInfo", notes=initialized)
            if any(not field(note, "Activation State") or not field(note, "Activation Evidence") for note in verified_notes):
                raise AnkiError("active-note initialization verification failed")
        if not schema_changed:
            client.call("sync")
        status = "local-complete-full-upload-required" if schema_changed else "complete"
        print(
            json.dumps(
                {
                    "schema": "vocab-activation-migration/v1",
                    "status": status,
                    "fields": verified_fields,
                    "initialized_note_ids": initialized,
                    "next_action": (
                        "Use Anki's Sync button and choose Upload to preserve the verified local schema migration; "
                        "this one-way sync choice requires explicit learner confirmation."
                        if schema_changed
                        else None
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except AnkiError as error:
        message = str(error)
        full_sync = "Sync status 2" in message or "ChangesRequired" in message
        print(
            json.dumps(
                {
                    "schema": "vocab-activation-migration/v1",
                    "status": "blocked-preexisting-full-sync" if full_sync else "error",
                    "error": message,
                    "next_action": (
                        "Resolve Anki's existing one-way full-sync choice before retrying; do not choose Upload or Download without the learner's direction."
                        if full_sync
                        else None
                    ),
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
