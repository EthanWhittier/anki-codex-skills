#!/usr/bin/env python3
"""Inspect durable Vocabulary state and emit the mastery-gated daily agenda."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, time, timedelta
from typing import Any

from vocab_runtime import (
    AnkiConnect,
    AnkiError,
    DEFAULT_URL,
    EXPECTED_FIELDS,
    INBOX_DECK,
    MASTER_DECK,
    MODEL,
    SUPPORT_DECK,
    USAGE_DECK,
    SchemaError,
    batched_info,
    cohort_start_from_tags,
    deck_role,
    derive_progress,
    field,
    parse_ledger,
    parse_state,
    voice_session_active,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    parser.add_argument("--no-sync", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    client = AnkiConnect(args.url, args.timeout)
    try:
        if not args.no_sync:
            client.call("sync")
        decks = set(client.call("deckNames") or [])
        if MASTER_DECK not in decks:
            output = {
                "schema": "codex-vocabulary-state/v2",
                "today": args.today.isoformat(),
                "setup": "missing-master-deck",
                "agenda": [{"priority": 1, "action": "setup", "reason": "Vocabulary deck is missing"}],
            }
            print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2))
            return 0

        model_fields = client.call("modelFieldNames", modelName=MODEL) or []
        if model_fields != EXPECTED_FIELDS:
            output = {
                "schema": "codex-vocabulary-state/v2",
                "today": args.today.isoformat(),
                "setup": "activation-schema-migration-required",
                "found_fields": model_fields,
                "expected_fields": EXPECTED_FIELDS,
                "agenda": [
                    {
                        "priority": 1,
                        "action": "request-schema-migration",
                        "reason": "durable mastery and Voice evidence fields are unavailable",
                    }
                ],
            }
            print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2))
            return 0

        note_ids = client.call("findNotes", query='deck:"Vocabulary"') or []
        notes = batched_info(client, "notesInfo", "notes", note_ids)
        card_ids = client.call("findCards", query='deck:"Vocabulary"') or []
        due_card_ids = set(client.call("findCards", query='deck:"Vocabulary" is:due') or [])
        new_card_ids = set(client.call("findCards", query='deck:"Vocabulary" is:new') or [])
        cards = batched_info(client, "cardsInfo", "cards", card_ids)

        cards_by_note: dict[int, list[dict[str, Any]]] = {}
        due_counts: Counter[str] = Counter()
        new_counts: Counter[str] = Counter()
        for card in cards:
            cards_by_note.setdefault(int(card["note"]), []).append(card)
            role = deck_role(str(card.get("deckName", "")))
            card_id = int(card["cardId"])
            if int(card.get("queue", 0)) == -1 or role == "inbox":
                continue
            if card_id in new_card_ids:
                new_counts[role] += 1
            elif card_id in due_card_ids:
                due_counts[role] += 1

        def state_item(
            note: dict[str, Any], state: dict[str, Any], progress: dict[str, Any], kind: str
        ) -> dict[str, Any]:
            pending_voice = [
                {
                    "session_id": session.get("session_id"),
                    "phase": session.get("phase"),
                    "tasks": session.get("tasks", []),
                    "missing_requirements": session.get("missing_requirements", []),
                    "created_at": session.get("created_at"),
                    "expires_at": session.get("expires_at"),
                }
                for session in state.get("pending_voice_sessions", [])
                if isinstance(session, dict) and voice_session_active(session)
            ]
            return {
                "kind": kind,
                "note_id": int(note["noteId"]),
                "lemma": field(note, "Lemma"),
                "sense_id": field(note, "Sense ID"),
                "goals": state.get("goals", []),
                "cohort_start": state.get("cohort_start"),
                "calendar_day": progress["calendar_day"],
                "phase": progress["current_phase"],
                "next_phase": progress["next_phase"],
                "unlocks_on": progress["unlocks_on"],
                "completed_phases": progress["completed_phases"],
                "missing_requirements": progress["missing"],
                "missing_tasks": progress["tasks"],
                "task_labels": progress["task_labels"],
                "voice_tasks": progress.get("voice_tasks", []),
                "voice_due": bool(progress.get("voice_due")),
                "voice_policy": progress.get("voice_policy"),
                "evidence_count": progress["evidence_count"],
                "today_evidence_count": progress["today_evidence_count"],
                "voice_evidence_count": progress["voice_evidence_count"],
                "voice_enabled": bool(state.get("voice_enabled") and "speech" in state.get("goals", [])),
                "recording_authorized": bool(state.get("recording_authorized")),
                "pending_voice_sessions": pending_voice,
                "last_session": state.get("last_session"),
            }

        active_items: list[dict[str, Any]] = []
        pronunciation_items: list[dict[str, Any]] = []
        for note in notes:
            tags = list(note.get("tags", []))
            if note.get("modelName") != MODEL:
                continue
            is_activation = "vocab::stage::activation" in tags
            has_state = bool(field(note, "Activation State"))
            if not is_activation and not has_state:
                continue
            started = cohort_start_from_tags(tags)
            state = parse_state(note, started)
            is_pronunciation_only = (
                state.get("status") == "pronunciation-only"
                and "vocab::stage::recognition" in tags
            )
            if not is_activation and not is_pronunciation_only:
                continue
            ledger = parse_ledger(note)
            progress = derive_progress(state, ledger, args.today)
            item = state_item(
                note,
                state,
                progress,
                "activation" if is_activation else "pronunciation-only",
            )
            if is_activation:
                active_items.append(item)
            elif progress["current_phase"] != "pronunciation-complete":
                pronunciation_items.append(item)

        candidates: list[dict[str, Any]] = []
        inbox_warnings: list[str] = []
        for note in notes:
            note_cards = cards_by_note.get(int(note["noteId"]), [])
            is_inbox = any(deck_role(str(card.get("deckName", ""))) == "inbox" for card in note_cards)
            if not is_inbox and field(note, "Learning Stage").casefold() != "candidate":
                continue
            suspended = bool(note_cards) and all(int(card.get("queue", 0)) == -1 for card in note_cards)
            candidate = {
                "note_id": int(note["noteId"]),
                "lemma": field(note, "Lemma") or field(note, "Front"),
                "has_context": bool(field(note, "Anchor Context")),
                "suspended": suspended,
            }
            candidates.append(candidate)
            if not suspended:
                inbox_warnings.append(f"candidate note {note['noteId']} has an active card")
        candidates.sort(key=lambda item: (not item["has_context"], item["note_id"]))

        recent_cutoff = int(datetime.combine(args.today - timedelta(days=6), time.min).timestamp() * 1000)
        recent_intake_count = sum(
            1
            for note in notes
            if note.get("modelName") == MODEL
            and field(note, "Learning Stage").casefold() not in {"", "candidate", "retired"}
            and int(note["noteId"]) >= recent_cutoff
        )

        due = {role: due_counts.get(role, 0) for role in ("recognition", "usage", "support")}
        new = {role: new_counts.get(role, 0) for role in ("recognition", "usage", "support")}
        agenda: list[dict[str, Any]] = []
        available_count = sum(due.values()) + sum(new.values())
        if available_count:
            agenda.append(
                {
                    "priority": len(agenda) + 1,
                    "action": "guided-anki-review",
                    "reason": "due, learning, or scheduler-available new cards exist",
                    "counts": {"due": due, "new_unscheduled_total": new},
                    "instruction": "Use chat-anki-review and preserve its ticketed, learner-rated scheduling flow.",
                }
            )

        voice_candidates = active_items + pronunciation_items
        pending_voice_items = [item for item in voice_candidates if item["pending_voice_sessions"]]
        voice_required_items = [
            item
            for item in voice_candidates
            if item["voice_due"] and not item["pending_voice_sessions"]
        ]
        practice_items = [
            item
            for item in active_items
            if item["phase"] not in {"spacing-hold", "decision-ready"}
            and not item["voice_due"]
            and not item["pending_voice_sessions"]
        ]
        decision_items = [item for item in active_items if item["phase"] == "decision-ready"]
        spacing_items = [item for item in active_items if item["phase"] == "spacing-hold"]
        if pending_voice_items:
            agenda.append(
                {
                    "priority": len(agenda) + 1,
                    "action": "voice-bridge-pending",
                    "reason": "a required or requested Voice packet is waiting for practice or report ingestion",
                    "items": pending_voice_items,
                    "instruction": "Recover the existing packet. Do not replace it silently. Ingest its complete report before advancing.",
                }
            )
        if voice_required_items:
            agenda.append(
                {
                    "priority": len(agenda) + 1,
                    "action": "voice-bridge-required",
                    "reason": "the current speech mastery gate requires evidence from audio Voice actually heard",
                    "items": voice_required_items,
                    "instruction": "Generate one packet directly. The user-started daily session authorizes that pending-session registration; if use is deferred, leave the gate due without penalty.",
                }
            )
        if practice_items:
            agenda.append(
                {
                    "priority": len(agenda) + 1,
                    "action": "activation-practice",
                    "reason": "mastery evidence remains incomplete for the current unlocked phase",
                    "items": practice_items,
                    "instruction": "Resume the first missing task. Record only validated non-sensitive evidence. A phase-matched Usage review can fulfill the same task; never duplicate it.",
                }
            )
        if decision_items:
            agenda.append(
                {
                    "priority": len(agenda) + 1,
                    "action": "cohort-decision",
                    "reason": "all mastery gates and minimum spacing are satisfied",
                    "items": decision_items,
                    "instruction": "Inspect evidence quality before guiding promote, extend, repair, or demote. Voice reports alone do not compel promotion.",
                }
            )

        intake_permitted = (
            bool(candidates)
            and not inbox_warnings
            and not decision_items
            and recent_intake_count < 7
            and sum(due.values()) <= 5
            and sum(new.values()) <= 3
            and len(active_items) <= 2
        )
        if intake_permitted:
            agenda.append(
                {
                    "priority": len(agenda) + 1,
                    "action": "onboard-inbox-candidate",
                    "reason": "the soft intake budget and current burden permit one candidate",
                    "candidate": candidates[0],
                }
            )
        if not agenda:
            agenda.append(
                {
                    "priority": 1,
                    "action": "capture-or-discover",
                    "reason": "no scheduled review, unlocked mastery work, or inbox intake is available",
                }
            )

        output = {
            "schema": "codex-vocabulary-state/v2",
            "today": args.today.isoformat(),
            "setup": "ready",
            "decks": {
                "master": MASTER_DECK in decks,
                "inbox": INBOX_DECK in decks,
                "usage": USAGE_DECK in decks,
                "support": SUPPORT_DECK in decks,
            },
            "review": {"due": due, "new_unscheduled_total": new},
            "intake": {
                "resolved_senses_added_last_7_calendar_days": recent_intake_count,
                "soft_weekly_budget": 7,
                "candidate_onboarding_permitted_today": intake_permitted,
            },
            "activation": {
                "count": len(active_items),
                "items": active_items,
                "spacing_holds": spacing_items,
                "voice_offshoot_available": any(item["voice_enabled"] for item in voice_candidates),
            },
            "pronunciation_checks": {
                "count": len(pronunciation_items),
                "items": pronunciation_items,
            },
            "inbox": {"count": len(candidates), "candidates": candidates, "warnings": inbox_warnings},
            "agenda": agenda,
            "caveats": [
                "new_unscheduled_total is inventory, not permission to bypass Anki daily limits",
                "calendar days unlock phases but never complete them; evidence controls advancement",
                "required Voice gates may be deferred or explicitly overridden, but they cannot be silently credited",
                "Voice transcripts may be approximate and Voice evidence is labeled separately",
            ],
        }
        print(json.dumps(output, ensure_ascii=False, indent=None if args.compact else 2))
        return 0
    except (AnkiError, SchemaError) as error:
        print(json.dumps({"schema": "codex-vocabulary-state/v2", "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
