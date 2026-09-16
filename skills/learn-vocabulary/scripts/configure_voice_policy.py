#!/usr/bin/env python3
"""Configure required, optional, waived, or pronunciation-only Vocabulary Voice work."""

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
    VOICE_GATE_TASKS,
    SchemaError,
    derive_progress,
    field,
    find_master_note,
    initial_ledger,
    initial_state,
    parse_ledger,
    parse_state,
    update_derived_state,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sense-id", required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--pronunciation-only", action="store_true")
    action.add_argument("--policy", choices=("required", "optional", "off"))
    action.add_argument("--waive-task", choices=sorted(VOICE_GATE_TASKS))
    action.add_argument("--clear-waiver", choices=sorted(VOICE_GATE_TASKS))
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--authorized-voice-policy-change", action="store_true")
    args = parser.parse_args()

    if not args.authorized_voice_policy_change:
        print(json.dumps({"error": "refusing write without --authorized-voice-policy-change"}))
        return 2

    client = AnkiConnect(args.url, args.timeout)
    try:
        client.call("sync")
        fields = client.call("modelFieldNames", modelName=MODEL) or []
        if fields != EXPECTED_FIELDS:
            raise AnkiError("Vocabulary Sense fields differ from the activation-ledger schema")
        note = find_master_note(client, args.sense_id)
        tags = set(note.get("tags", []))
        state_text = field(note, "Activation State")
        ledger_text = field(note, "Activation Evidence")

        if args.pronunciation_only:
            if "vocab::stage::recognition" not in tags:
                raise AnkiError("pronunciation-only Voice checks require a recognition-stage master note")
            if state_text:
                state = parse_state(note)
                if state.get("status") != "pronunciation-only":
                    raise AnkiError("the note already has a different activation state")
                ledger = parse_ledger(note)
            else:
                state = initial_state(
                    args.sense_id,
                    date.today(),
                    goals=["speech"],
                    recording_authorized=True,
                    voice_enabled=True,
                )
                state["status"] = "pronunciation-only"
                state["voice_policy"] = "required"
                ledger = initial_ledger(args.sense_id)
        else:
            if not state_text or not ledger_text:
                raise AnkiError("the note has no durable Voice or activation state to configure")
            state = parse_state(note)
            ledger = parse_ledger(note)
            waivers = set(state.get("voice_waivers", []))
            if args.policy:
                state["voice_policy"] = args.policy
                state["voice_enabled"] = args.policy != "off"
                if args.policy == "off":
                    waivers.update(VOICE_GATE_TASKS)
            elif args.waive_task:
                waivers.add(args.waive_task)
            elif args.clear_waiver:
                waivers.discard(args.clear_waiver)
            state["voice_waivers"] = sorted(waivers)

        state = update_derived_state(state, ledger, date.today(), [])
        note_id = int(note["noteId"])
        client.call(
            "updateNoteFields",
            note={
                "id": note_id,
                "fields": {
                    "Activation State": json.dumps(state, ensure_ascii=False, separators=(",", ":")),
                    "Activation Evidence": json.dumps(ledger, ensure_ascii=False, separators=(",", ":")),
                },
            },
        )
        verified = client.call("notesInfo", notes=[note_id]) or []
        if len(verified) != 1:
            raise AnkiError("Voice policy verification could not recover the updated note")
        verified_state = parse_state(verified[0])
        verified_ledger = parse_ledger(verified[0])
        progress = derive_progress(verified_state, verified_ledger, date.today())
        client.call("sync")
        print(
            json.dumps(
                {
                    "schema": "vocab-voice-policy/v1",
                    "status": "updated",
                    "sense_id": args.sense_id,
                    "note_id": note_id,
                    "profile": progress.get("profile"),
                    "voice_policy": progress.get("voice_policy"),
                    "voice_waivers": verified_state.get("voice_waivers", []),
                    "current_phase": progress.get("current_phase"),
                    "voice_due": progress.get("voice_due", False),
                    "voice_tasks": progress.get("voice_tasks", []),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (AnkiError, SchemaError) as error:
        print(json.dumps({"schema": "vocab-voice-policy/v1", "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
