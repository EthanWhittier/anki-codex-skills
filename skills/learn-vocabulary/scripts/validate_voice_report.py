#!/usr/bin/env python3
"""Validate a pasted Voice bridge report and emit reviewable evidence candidates without writing."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from record_evidence import normalize_event
from vocab_runtime import (
    AnkiConnect,
    AnkiError,
    DEFAULT_URL,
    EXPECTED_FIELDS,
    MODEL,
    SchemaError,
    derive_progress,
    find_master_note,
    parse_datetime,
    parse_ledger,
    parse_state,
    voice_session_active,
)


REPORT_SCHEMA = "vocab-voice-bridge/v1"


def load_report(value: str) -> dict[str, Any]:
    text = value.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Voice bridge report must be one JSON object")
    return parsed


def require_text(value: Any, label: str, maximum: int = 200) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum:
        raise ValueError(f"{label} must contain 1–{maximum} characters")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--no-sync", action="store_true")
    args = parser.parse_args()

    try:
        report = load_report(args.report_json)
        if report.get("schema") != REPORT_SCHEMA:
            raise ValueError(f"expected schema {REPORT_SCHEMA}")
        session_id = require_text(report.get("session_id"), "session_id")
        if not re.fullmatch(r"voice-\d{4}-\d{2}-\d{2}-[a-f0-9]{8}", session_id):
            raise ValueError("session_id has an unexpected format")
        fingerprint = require_text(report.get("prompt_fingerprint"), "prompt_fingerprint")
        if not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
            raise ValueError("prompt_fingerprint must be a lowercase SHA-256 digest")
        report_items = report.get("items")
        if not isinstance(report_items, list) or len(report_items) != 1:
            raise ValueError("items must contain exactly one item report")
    except (json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"schema": REPORT_SCHEMA, "status": "rejected", "error": str(error)}))
        return 2

    client = AnkiConnect(args.url, args.timeout)
    try:
        if not args.no_sync:
            client.call("sync")
        fields = client.call("modelFieldNames", modelName=MODEL) or []
        if fields != EXPECTED_FIELDS:
            raise AnkiError("Vocabulary Sense fields differ from the activation-ledger schema")

        candidate_events: list[dict[str, Any]] = []
        review_material: list[dict[str, Any]] = []
        seen_senses: set[str] = set()
        for item in report_items:
            if not isinstance(item, dict):
                raise ValueError("each item report must be an object")
            sense_id = require_text(item.get("sense_id"), "sense_id")
            if sense_id in seen_senses:
                raise ValueError(f"duplicate Voice item for {sense_id}")
            seen_senses.add(sense_id)
            note = find_master_note(client, sense_id)
            state = parse_state(note)
            progress = derive_progress(state, parse_ledger(note), date.today())
            pending = next(
                (
                    entry
                    for entry in state.get("pending_voice_sessions", [])
                    if isinstance(entry, dict)
                    and entry.get("session_id") == session_id
                    and entry.get("prompt_fingerprint") == fingerprint
                ),
                None,
            )
            if pending is None:
                raise ValueError(f"no matching durable Voice session for {sense_id}")
            now = datetime.now().astimezone()
            if not voice_session_active(pending, now):
                raise ValueError(f"Voice session for {sense_id} has expired")
            reported_occurred = report.get("occurred_at")
            occurred = parse_datetime(reported_occurred)
            if occurred is None:
                raise ValueError(
                    f"Voice report needs the actual timezone-aware practice-completion timestamp for {sense_id}"
                )
            created = parse_datetime(pending.get("created_at"))
            expires = parse_datetime(pending.get("expires_at"))
            if created is None or occurred < created - timedelta(minutes=5):
                raise ValueError(f"Voice report for {sense_id} predates its session")
            if occurred > now + timedelta(minutes=10) or (expires is not None and occurred > expires):
                raise ValueError(f"Voice report for {sense_id} is outside its session window")
            phase = require_text(item.get("phase"), "phase")
            if phase != pending.get("phase"):
                raise ValueError(f"Voice phase mismatch for {sense_id}")
            if phase != progress["current_phase"]:
                raise ValueError(f"Voice session for {sense_id} is stale; current phase is {progress['current_phase']}")
            if list(pending.get("missing_requirements", [])) != list(progress["missing"]):
                raise ValueError(f"Voice session for {sense_id} is stale because its missing-task state changed")
            allowed_tasks = set(pending.get("tasks", []))
            integrity = item.get("integrity")
            if not isinstance(integrity, dict):
                raise ValueError(f"integrity is missing for {sense_id}")
            leaked = integrity.get("target_revealed_early")
            audio_heard = integrity.get("audio_heard")
            if leaked not in {True, False, None} or audio_heard not in {True, False, None}:
                raise ValueError(f"integrity booleans are invalid for {sense_id}")
            if integrity.get("transcript_may_be_approximate") is not True:
                raise ValueError(f"transcript uncertainty was not acknowledged for {sense_id}")
            tasks = item.get("tasks")
            if not isinstance(tasks, list) or not tasks:
                raise ValueError(f"tasks are missing for {sense_id}")

            expected_visibility = "hidden" if phase in {"lexical-access", "integration"} else "visible"
            seen_tasks: set[str] = set()
            for task_report in tasks:
                if not isinstance(task_report, dict):
                    raise ValueError(f"task report must be an object for {sense_id}")
                task = require_text(task_report.get("task"), "task")
                if task in seen_tasks:
                    raise ValueError(f"duplicate task {task} for {sense_id}")
                seen_tasks.add(task)
                if task not in allowed_tasks:
                    raise ValueError(f"task {task} was not assigned in Voice session {session_id}")
                if task_report.get("modality") != "speech":
                    raise ValueError(f"Voice modality must be speech for {sense_id}/{task}")
                visibility = require_text(task_report.get("target_visibility"), "target_visibility")
                if visibility != expected_visibility:
                    raise ValueError(f"target visibility mismatch for {sense_id}/{task}")
                approximate_response = str(task_report.get("approximate_final_response") or "").strip()
                coach_notes = str(task_report.get("coach_notes") or "").strip()
                if len(approximate_response) > 1000 or len(coach_notes) > 1000:
                    raise ValueError("Voice review text is unexpectedly long")
                if not coach_notes:
                    raise ValueError(f"coach_notes are required for {sense_id}/{task}")
                if task_report.get("result") in {"pass", "partial"} and not approximate_response:
                    raise ValueError(f"a pass or partial result requires an approximate response for {sense_id}/{task}")
                if task == "integration-speech" and task_report.get("result") == "pass" and task_report.get("novel_context") is not True:
                    raise ValueError(f"integration-speech pass requires a novel context for {sense_id}")
                raw_event = {
                    "occurred_at": occurred.isoformat(timespec="seconds"),
                    "source": "chatgpt-voice-bridge",
                    "evidence_quality": "voice-report",
                    "phase": phase,
                    "task": task,
                    "modality": "speech",
                    "target_visibility": visibility,
                    "result": task_report.get("result"),
                    "count": task_report.get("count", 1),
                    "context_keys": task_report.get("context_keys", []),
                    "novel_context": task_report.get("novel_context", False),
                    "target_retrieved_before_reveal": task_report.get("target_retrieved_before_reveal"),
                    "target_revealed_early": leaked,
                    "audio_heard": audio_heard,
                    "pronunciation": task_report.get("pronunciation", "not-assessed"),
                    "errors": task_report.get("errors", []),
                    "bridge_session_id": session_id,
                    "prompt_fingerprint": fingerprint,
                    "semantic_reviewed": False,
                    "notes": "Voice bridge structurally validated; semantic review pending.",
                }
                normalized = normalize_event(raw_event, sense_id, require_voice_review=False)
                normalized.pop("id", None)
                candidate_events.append(normalized)
                review_material.append(
                    {
                        "sense_id": sense_id,
                        "task": task,
                        "reported_result": task_report.get("result"),
                        "normalized_result": normalized["result"],
                        "approximate_final_response": approximate_response,
                        "coach_notes": coach_notes,
                        "semantic_review_required": True,
                    }
                )
            if seen_tasks != allowed_tasks:
                missing = sorted(allowed_tasks - seen_tasks)
                extra = sorted(seen_tasks - allowed_tasks)
                raise ValueError(
                    f"Voice report task batch mismatch for {sense_id}; missing={missing}, extra={extra}"
                )

        print(
            json.dumps(
                {
                    "schema": REPORT_SCHEMA,
                    "status": "structurally-valid",
                    "session_id": session_id,
                    "candidate_events": candidate_events,
                    "review_material": review_material,
                    "next_step": "Semantically review every candidate, preserve fail/unverified outcomes, then submit the complete assigned task set as one atomic batch.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (AnkiError, SchemaError, TypeError, ValueError) as error:
        print(json.dumps({"schema": REPORT_SCHEMA, "status": "rejected", "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
