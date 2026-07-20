#!/usr/bin/env python3
"""Append validated non-sensitive activation evidence and update mastery state."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from vocab_runtime import (
    AnkiConnect,
    AnkiError,
    DEFAULT_URL,
    EVIDENCE_SCHEMA,
    EXPECTED_FIELDS,
    MODEL,
    PHASES,
    TASK_PHASE,
    SchemaError,
    derive_progress,
    field,
    find_master_note,
    parse_ledger,
    parse_datetime,
    parse_state,
    slug,
    update_derived_state,
    voice_session_active,
)


TASKS = {
    "meaning-boundary",
    "pronunciation",
    "visible-use",
    "neighbor-distinction",
    "grammar-collocation",
    "misuse-diagnosis",
    "controlled-use",
    "hidden-retrieval",
    "integration-speech",
    "integration-writing",
    "delayed-definition",
}
SOURCES = {"codex-chat", "chatgpt-voice-bridge", "real-world-report", "anki-review"}
QUALITIES = {"direct-chat", "voice-report", "self-report", "anki-scheduling"}
SOURCE_QUALITY = {
    "codex-chat": "direct-chat",
    "chatgpt-voice-bridge": "voice-report",
    "real-world-report": "self-report",
    "anki-review": "anki-scheduling",
}
MODALITIES = {"speech", "writing", "mixed", "recognition"}
VISIBILITY = {"visible", "hidden", "not-applicable"}
RESULTS = {"pass", "partial", "fail", "unverified"}
PRONUNCIATION = {"pass", "needs-work", "not-assessed"}
ERRORS = {
    "wrong-sense",
    "definition",
    "lexical-access",
    "collocation",
    "grammar-frame",
    "register",
    "pronunciation",
    "prompt-quality",
}
TASK_MAX_COUNT = {task: 1 for task in TASKS}
TASK_MAX_COUNT.update({"visible-use": 2, "controlled-use": 3})


def fail(message: str) -> ValueError:
    return ValueError(message)


def parse_timestamp(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return datetime.now().astimezone().isoformat(timespec="seconds")
    candidate = text.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(candidate)
    except ValueError as error:
        raise fail(f"invalid occurred_at: {text}") from error
    return text


def normalize_event(
    raw: dict[str, Any], sense_id: str, require_voice_review: bool = True
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise fail("each event must be an object")
    source = str(raw.get("source", ""))
    quality = str(raw.get("evidence_quality", ""))
    phase = str(raw.get("phase", ""))
    task = str(raw.get("task", ""))
    modality = str(raw.get("modality", ""))
    visibility = str(raw.get("target_visibility", ""))
    result = str(raw.get("result", ""))
    pronunciation = str(raw.get("pronunciation", "not-assessed"))
    if source not in SOURCES:
        raise fail(f"unsupported source: {source}")
    if quality not in QUALITIES:
        raise fail(f"unsupported evidence_quality: {quality}")
    if quality != SOURCE_QUALITY[source]:
        raise fail(f"source {source} requires evidence_quality {SOURCE_QUALITY[source]}")
    if phase not in PHASES:
        raise fail(f"unsupported phase: {phase}")
    if task not in TASKS:
        raise fail(f"unsupported task: {task}")
    if TASK_PHASE[task] != phase:
        raise fail(f"task {task} belongs to phase {TASK_PHASE[task]}, not {phase}")
    if modality not in MODALITIES:
        raise fail(f"unsupported modality: {modality}")
    if visibility not in VISIBILITY:
        raise fail(f"unsupported target_visibility: {visibility}")
    if result not in RESULTS:
        raise fail(f"unsupported result: {result}")
    if pronunciation not in PRONUNCIATION:
        raise fail(f"unsupported pronunciation: {pronunciation}")

    count = int(raw.get("count", 1))
    if not 1 <= count <= TASK_MAX_COUNT[task]:
        raise fail(f"count for {task} must be from 1 to {TASK_MAX_COUNT[task]}")
    context_keys = raw.get("context_keys", [])
    if not isinstance(context_keys, list) or len(context_keys) > 10:
        raise fail("context_keys must be a list of at most 10 coarse labels")
    context_keys = list(dict.fromkeys(slug(str(value)) for value in context_keys if str(value).strip()))
    if result in {"pass", "partial"} and task in {"visible-use", "controlled-use"} and len(context_keys) < count:
        raise fail(f"{task} requires at least one distinct coarse context label per counted use")
    errors = raw.get("errors", [])
    if not isinstance(errors, list) or any(error not in ERRORS for error in errors):
        raise fail("errors contains an unsupported value")
    notes = str(raw.get("notes", "")).strip()
    if len(notes) > 300:
        raise fail("notes must be 300 characters or fewer and contain no raw transcript")

    occurred_at = parse_timestamp(raw.get("occurred_at"))
    target_retrieved = raw.get("target_retrieved_before_reveal")
    if target_retrieved not in {True, False, None}:
        raise fail("target_retrieved_before_reveal must be true, false, or null")
    reported_leak = raw.get("target_revealed_early", False)
    if reported_leak not in {True, False, None}:
        raise fail("target_revealed_early must be true, false, or null")
    target_revealed_early = bool(reported_leak)
    audio_heard = raw.get("audio_heard")
    if audio_heard not in {True, False, None}:
        raise fail("audio_heard must be true, false, or null")
    novel_context = raw.get("novel_context", False)
    if novel_context not in {True, False}:
        raise fail("novel_context must be true or false")

    if task in {"hidden-retrieval", "integration-speech", "integration-writing"} and (
        visibility != "hidden" or target_retrieved is not True or reported_leak is not False
    ):
        result = "unverified" if result == "pass" else result
    if source == "chatgpt-voice-bridge":
        if modality != "speech":
            raise fail("ChatGPT Voice bridge evidence must use speech modality")
        if modality == "speech" and audio_heard is not True:
            pronunciation = "not-assessed"
            result = "unverified"
    if task == "pronunciation" and result == "pass":
        if modality not in {"speech", "mixed"} or audio_heard is not True:
            result = "unverified"
            pronunciation = "not-assessed"
        elif pronunciation != "pass":
            result = "partial"

    bridge_session_id = str(raw.get("bridge_session_id", "")).strip() or None
    prompt_fingerprint = str(raw.get("prompt_fingerprint", "")).strip() or None
    semantic_reviewed = raw.get("semantic_reviewed", False)
    if semantic_reviewed not in {True, False}:
        raise fail("semantic_reviewed must be true or false")
    if source == "chatgpt-voice-bridge":
        if not bridge_session_id or not re.fullmatch(r"voice-\d{4}-\d{2}-\d{2}-[a-f0-9]{8}", bridge_session_id):
            raise fail("Voice bridge evidence requires a canonical bridge_session_id")
        if not prompt_fingerprint or not re.fullmatch(r"[a-f0-9]{64}", prompt_fingerprint):
            raise fail("Voice bridge evidence requires a valid prompt_fingerprint")
        if require_voice_review and semantic_reviewed is not True:
            raise fail("Voice bridge evidence requires completed semantic review")
    event = {
        "occurred_at": occurred_at,
        "source": source,
        "evidence_quality": quality,
        "phase": phase,
        "task": task,
        "modality": modality,
        "target_visibility": visibility,
        "result": result,
        "count": count,
        "context_keys": context_keys,
        "novel_context": novel_context,
        "target_retrieved_before_reveal": target_retrieved,
        "target_revealed_early": target_revealed_early,
        "audio_heard": audio_heard,
        "pronunciation": pronunciation,
        "errors": list(dict.fromkeys(errors)),
        "bridge_session_id": bridge_session_id,
        "prompt_fingerprint": prompt_fingerprint,
        "semantic_reviewed": bool(semantic_reviewed),
        "notes": notes,
    }
    identity_seed = json.dumps({"sense_id": sense_id, **event}, sort_keys=True)
    event["id"] = str(raw.get("id", "")).strip() or "evt-" + hashlib.sha256(identity_seed.encode()).hexdigest()[:20]
    return {"id": event.pop("id"), **event}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sense-id", required=True)
    parser.add_argument("--events-json", required=True, help="A JSON event object or list of event objects.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--authorized-evidence-record", action="store_true")
    args = parser.parse_args()

    if not args.authorized_evidence_record:
        print(json.dumps({"error": "refusing write without --authorized-evidence-record"}))
        return 2
    try:
        payload = json.loads(args.events_json)
        raw_events = payload if isinstance(payload, list) else [payload]
        events = [normalize_event(raw, args.sense_id) for raw in raw_events]
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        print(json.dumps({"error": str(error)}))
        return 2

    client = AnkiConnect(args.url, args.timeout)
    try:
        client.call("sync")
        model_fields = client.call("modelFieldNames", modelName=MODEL) or []
        if model_fields != EXPECTED_FIELDS:
            raise AnkiError("Vocabulary Sense fields differ from the activation-ledger schema; no write made")
        note = find_master_note(client, args.sense_id)
        state = parse_state(note)
        if not state.get("recording_authorized"):
            raise AnkiError("Activation State does not contain standing evidence-recording authorization")
        ledger = parse_ledger(note)
        existing_ids = {str(event.get("id")) for event in ledger.get("events", []) if isinstance(event, dict)}
        added = [event for event in events if event["id"] not in existing_ids]
        if not added:
            output = {
                "schema": EVIDENCE_SCHEMA,
                "status": "duplicate-noop",
                "sense_id": args.sense_id,
                "event_ids": [event["id"] for event in events],
                "progress": derive_progress(state, ledger, date.today()),
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0
        now = datetime.now().astimezone()
        current_progress = derive_progress(state, ledger, date.today())
        voice_groups: dict[str, list[dict[str, Any]]] = {}
        for event in added:
            if event.get("source") == "chatgpt-voice-bridge":
                voice_groups.setdefault(str(event.get("bridge_session_id")), []).append(event)
        for session_id, session_events in voice_groups.items():
            task_keys = [str(event.get("task")) for event in session_events]
            if len(task_keys) != len(set(task_keys)):
                raise AnkiError(f"Voice session {session_id} contains duplicate task events")
            fingerprints = {str(event.get("prompt_fingerprint")) for event in session_events}
            if len(fingerprints) != 1:
                raise AnkiError(f"Voice session {session_id} contains inconsistent fingerprints")
            pending_session = next(
                (
                    session
                    for session in state.get("pending_voice_sessions", [])
                    if isinstance(session, dict)
                    and session.get("session_id") == session_id
                    and session.get("prompt_fingerprint") in fingerprints
                ),
                None,
            )
            if pending_session is None or not voice_session_active(pending_session, now):
                raise AnkiError(f"Voice session {session_id} is not active")
            if pending_session.get("phase") != current_progress["current_phase"]:
                raise AnkiError(
                    f"Voice session {session_id} is stale; current phase is {current_progress['current_phase']}"
                )
            if list(pending_session.get("missing_requirements", [])) != list(current_progress["missing"]):
                raise AnkiError(f"Voice session {session_id} is stale because its missing-task state changed")
            assigned_tasks = list(pending_session.get("tasks", []))
            if len(assigned_tasks) != len(set(assigned_tasks)) or set(task_keys) != set(assigned_tasks):
                raise AnkiError(f"Voice session {session_id} must be recorded once as its complete task batch")
        for event in added:
            if event.get("source") != "chatgpt-voice-bridge":
                continue
            pending = next(
                (
                    session
                    for session in state.get("pending_voice_sessions", [])
                    if isinstance(session, dict)
                    and session.get("session_id") == event.get("bridge_session_id")
                    and session.get("prompt_fingerprint") == event.get("prompt_fingerprint")
                    and session.get("phase") == event.get("phase")
                    and event.get("task") in session.get("tasks", [])
                ),
                None,
            )
            if pending is None or not voice_session_active(pending, now):
                raise AnkiError("Voice evidence does not match an active pending session")
            occurred = parse_datetime(event.get("occurred_at"))
            created = parse_datetime(pending.get("created_at"))
            expires = parse_datetime(pending.get("expires_at"))
            if occurred is None or created is None or occurred < created - timedelta(minutes=5):
                raise AnkiError("Voice evidence timestamp predates its pending session")
            if occurred > now + timedelta(minutes=10) or (expires is not None and occurred > expires):
                raise AnkiError("Voice evidence timestamp is outside its session window")
        ledger["events"].extend(added)
        state = update_derived_state(state, ledger, date.today(), added)
        completed_voice_sessions = {
            str(event.get("bridge_session_id"))
            for event in added
            if event.get("source") == "chatgpt-voice-bridge" and event.get("bridge_session_id")
        }
        if completed_voice_sessions:
            pending = state.get("pending_voice_sessions", [])
            state["pending_voice_sessions"] = [
                session
                for session in pending
                if str(session.get("session_id")) not in completed_voice_sessions
            ]
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
        months = {event["occurred_at"][:7] for event in added}
        tag_values: list[str] = []
        if any(event["modality"] in {"speech", "mixed"} for event in added):
            tag_values.extend(f"vocab::evidence::spoken::{month}" for month in months)
        if any(event["modality"] in {"writing", "mixed"} for event in added):
            tag_values.extend(f"vocab::evidence::written::{month}" for month in months)
        if tag_values:
            client.call("getTags")
            client.call("addTags", notes=[note_id], tags=" ".join(sorted(set(tag_values))))

        verified = client.call("notesInfo", notes=[note_id])[0]
        verified_state = parse_state(verified)
        verified_ledger = parse_ledger(verified)
        verified_ids = {str(event.get("id")) for event in verified_ledger["events"]}
        if not all(event["id"] in verified_ids for event in added):
            raise AnkiError("evidence verification failed")
        client.call("sync")
        output = {
            "schema": EVIDENCE_SCHEMA,
            "status": "recorded",
            "sense_id": args.sense_id,
            "note_id": note_id,
            "event_ids": [event["id"] for event in added],
            "progress": derive_progress(verified_state, verified_ledger, date.today()),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (AnkiError, SchemaError) as error:
        print(json.dumps({"schema": EVIDENCE_SCHEMA, "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
