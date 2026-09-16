#!/usr/bin/env python3
"""Shared runtime primitives for the durable Vocabulary controller."""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any, Iterable


DEFAULT_URL = "http://127.0.0.1:8765"
MASTER_DECK = "Vocabulary"
INBOX_DECK = "Vocabulary::Inbox"
USAGE_DECK = "Vocabulary::Usage"
SUPPORT_DECK = "Vocabulary::Support"
MODEL = "Vocabulary Sense"

EXPECTED_FIELDS = [
    "Front",
    "Back",
    "AI Grader Instructions",
    "Lemma",
    "Part of Speech",
    "Sense ID",
    "Pronunciation",
    "Authoritative Definition",
    "Definition Citation",
    "Required Components",
    "Working Gloss",
    "Anchor Context",
    "Grounding and Boundaries",
    "Usage",
    "Related Senses",
    "Source Encounter",
    "Learning Stage",
    "Activation State",
    "Activation Evidence",
]

STATE_SCHEMA = "vocab-activation-state/v1"
EVIDENCE_SCHEMA = "vocab-activation-evidence/v1"
PHASES = ["anchor", "distinguish", "controlled-production", "lexical-access", "integration"]
TASK_PHASE = {
    "meaning-boundary": "anchor",
    "pronunciation": "anchor",
    "visible-use": "anchor",
    "neighbor-distinction": "distinguish",
    "grammar-collocation": "distinguish",
    "misuse-diagnosis": "distinguish",
    "controlled-use": "controlled-production",
    "hidden-retrieval": "lexical-access",
    "integration-speech": "integration",
    "integration-writing": "integration",
    "delayed-definition": "integration",
}
PHASE_MIN_DAY = {
    "anchor": 1,
    "distinguish": 3,
    "controlled-production": 6,
    "lexical-access": 10,
    "integration": 13,
    "decision-ready": 15,
}
VOICE_SESSION_MAX_AGE = timedelta(hours=48)
TASK_LABELS = {
    "meaning-boundary": "explain the selected sense and its main boundary",
    "pronunciation": "say the target aloud and receive pronunciation feedback",
    "visible-use": "produce natural uses with the target visible",
    "neighbor-distinction": "distinguish the target from its main near-neighbor",
    "grammar-collocation": "use a verified grammatical frame or collocation",
    "misuse-diagnosis": "diagnose one non-example or misuse",
    "controlled-use": "produce natural uses across varied contexts and modalities",
    "hidden-retrieval": "retrieve the target from communicative intent while it is hidden",
    "integration-speech": "use the target in a 30–60 second spoken response",
    "integration-writing": "use the target in a short novel-context paragraph",
    "delayed-definition": "recover the required meaning components after a delay",
}
VOICE_POLICIES = {"required", "optional", "off"}
VOICE_GATE_TASKS = {"pronunciation", "hidden-retrieval", "integration-speech"}


class AnkiError(RuntimeError):
    pass


class SchemaError(RuntimeError):
    pass


class AnkiConnect:
    def __init__(self, url: str = DEFAULT_URL, timeout: float = 15.0) -> None:
        self.url = url
        self.timeout = timeout

    def call(self, action: str, **params: Any) -> Any:
        payload: dict[str, Any] = {"action": action, "version": 6}
        if params:
            payload["params"] = params
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except Exception as error:
            raise AnkiError(f"failed to reach AnkiConnect at {self.url}: {error}") from error
        if result.get("error") is not None:
            raise AnkiError(f"AnkiConnect {action} failed: {result['error']}")
        return result.get("result")


def chunks(values: list[int], size: int = 100) -> Iterable[list[int]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def batched_info(client: AnkiConnect, action: str, key: str, ids: list[int]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for batch in chunks(ids):
        output.extend(client.call(action, **{key: batch}) or [])
    return output


def field(note: dict[str, Any], name: str) -> str:
    value = note.get("fields", {}).get(name, "")
    if isinstance(value, dict):
        value = value.get("value", "")
    return str(value).strip()


def parse_object(value: str, schema: str, empty: dict[str, Any]) -> dict[str, Any]:
    if not value:
        return dict(empty)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise SchemaError(f"invalid JSON for {schema}: {error}") from error
    if not isinstance(parsed, dict) or parsed.get("schema") != schema:
        raise SchemaError(f"expected {schema}")
    return parsed


def normalize_goals(goals: Any) -> list[str]:
    if not isinstance(goals, list):
        return ["writing"]
    normalized = [goal for goal in goals if goal in {"speech", "writing"}]
    return list(dict.fromkeys(normalized)) or ["writing"]


def voice_policy(state: dict[str, Any]) -> str:
    raw = str(state.get("voice_policy", "")).strip().casefold()
    if raw in VOICE_POLICIES:
        return raw
    goals = normalize_goals(state.get("goals"))
    if state.get("status") == "pronunciation-only":
        return "required"
    return "required" if state.get("voice_enabled") and "speech" in goals else "optional"


def voice_waivers(state: dict[str, Any]) -> set[str]:
    raw = state.get("voice_waivers", [])
    if not isinstance(raw, list):
        return set()
    return {str(task) for task in raw if str(task) in VOICE_GATE_TASKS}


def voice_required(state: dict[str, Any], task: str) -> bool:
    if task not in VOICE_GATE_TASKS or voice_policy(state) != "required":
        return False
    if task in voice_waivers(state):
        return False
    if state.get("status") == "pronunciation-only":
        return task == "pronunciation"
    return "speech" in normalize_goals(state.get("goals"))


def cohort_start_from_tags(tags: list[str]) -> date | None:
    prefix = "vocab::cohort::"
    values: list[date] = []
    for tag in tags:
        if not tag.startswith(prefix):
            continue
        try:
            values.append(datetime.strptime(tag[len(prefix) :], "%Y-%m-%d").date())
        except ValueError:
            continue
    return min(values) if values else None


def initial_state(
    sense_id: str,
    cohort_start: date,
    goals: list[str] | None = None,
    recording_authorized: bool = False,
    voice_enabled: bool = False,
) -> dict[str, Any]:
    normalized_goals = normalize_goals(goals or ["writing"])
    return {
        "schema": STATE_SCHEMA,
        "sense_id": sense_id,
        "goals": normalized_goals,
        "cohort_start": cohort_start.isoformat(),
        "status": "active",
        "current_phase": "anchor",
        "phase_started": cohort_start.isoformat(),
        "completed_phases": [],
        "recording_authorized": bool(recording_authorized),
        "voice_enabled": bool(voice_enabled),
        "voice_policy": "required" if voice_enabled and "speech" in normalized_goals else "optional",
        "voice_waivers": [],
        "pending_voice_sessions": [],
        "last_evidence_at": None,
        "last_session": None,
    }


def initial_ledger(sense_id: str) -> dict[str, Any]:
    return {"schema": EVIDENCE_SCHEMA, "sense_id": sense_id, "events": []}


def parse_state(note: dict[str, Any], fallback_start: date | None = None) -> dict[str, Any]:
    sense_id = field(note, "Sense ID")
    started = fallback_start or cohort_start_from_tags(list(note.get("tags", []))) or date.today()
    state = parse_object(
        field(note, "Activation State"),
        STATE_SCHEMA,
        initial_state(sense_id, started),
    )
    if state.get("sense_id") != sense_id:
        raise SchemaError("Activation State Sense ID does not match its note")
    pending = state.get("pending_voice_sessions", [])
    if not isinstance(pending, list):
        raise SchemaError("Activation State pending_voice_sessions must be a list")
    policy = str(state.get("voice_policy", "")).strip().casefold()
    if policy and policy not in VOICE_POLICIES:
        raise SchemaError("Activation State voice_policy is invalid")
    waivers = state.get("voice_waivers", [])
    if not isinstance(waivers, list) or any(str(task) not in VOICE_GATE_TASKS for task in waivers):
        raise SchemaError("Activation State voice_waivers is invalid")
    state["voice_policy"] = voice_policy(state)
    state["voice_waivers"] = sorted(voice_waivers(state))
    return state


def parse_ledger(note: dict[str, Any]) -> dict[str, Any]:
    sense_id = field(note, "Sense ID")
    ledger = parse_object(field(note, "Activation Evidence"), EVIDENCE_SCHEMA, initial_ledger(sense_id))
    events = ledger.get("events")
    if not isinstance(events, list):
        raise SchemaError("Activation Evidence events must be a list")
    if ledger.get("sense_id") != sense_id:
        raise SchemaError("Activation Evidence Sense ID does not match its note")
    return ledger


def event_date(event: dict[str, Any]) -> date | None:
    value = str(event.get("occurred_at", ""))
    if len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def voice_session_active(session: dict[str, Any], now: datetime | None = None) -> bool:
    now = now or datetime.now().astimezone()
    created = parse_datetime(session.get("created_at"))
    expires = parse_datetime(session.get("expires_at"))
    if created is None:
        return False
    if expires is None:
        expires = created + VOICE_SESSION_MAX_AGE
    return created - timedelta(minutes=5) <= now <= expires


def passed(events: list[dict[str, Any]], task: str) -> list[dict[str, Any]]:
    return [event for event in events if event.get("task") == task and event.get("result") == "pass"]


def count_events(events: list[dict[str, Any]], task: str) -> int:
    return sum(max(1, int(event.get("count", 1))) for event in passed(events, task))


def voice_passed(events: list[dict[str, Any]], task: str) -> list[dict[str, Any]]:
    result = [
        event
        for event in passed(events, task)
        if event.get("source") == "chatgpt-voice-bridge"
        and event.get("evidence_quality") == "voice-report"
        and event.get("audio_heard") is True
    ]
    if task == "pronunciation":
        result = [event for event in result if event.get("pronunciation") == "pass"]
    return result


def direct_passed(events: list[dict[str, Any]], task: str) -> list[dict[str, Any]]:
    return [event for event in passed(events, task) if event.get("evidence_quality") != "voice-report"]


def modalities(events: list[dict[str, Any]], task: str) -> set[str]:
    return {str(event.get("modality")) for event in passed(events, task)}


def contexts(events: list[dict[str, Any]], task: str) -> set[str]:
    result: set[str] = set()
    for event in passed(events, task):
        values = event.get("context_keys", [])
        if isinstance(values, list):
            result.update(str(value) for value in values if value)
    return result


def phase_audit(
    events: list[dict[str, Any]], goals: list[str], state: dict[str, Any] | None = None
) -> dict[str, dict[str, Any]]:
    goals = normalize_goals(goals)
    state = state or {"goals": goals, "voice_enabled": False, "voice_policy": "optional"}
    audits: dict[str, dict[str, Any]] = {}

    anchor_missing: list[str] = []
    if count_events(events, "meaning-boundary") < 1:
        anchor_missing.append("meaning-boundary")
    if (
        "speech" in goals
        and "pronunciation" not in voice_waivers(state)
        and count_events(events, "pronunciation") < 1
    ):
        anchor_missing.append("pronunciation")
    if "speech" in goals and voice_required(state, "pronunciation") and not voice_passed(events, "pronunciation"):
        anchor_missing.append("voice-pronunciation")
    if count_events(events, "visible-use") < 2:
        anchor_missing.append("visible-use")
    audits["anchor"] = {"complete": not anchor_missing, "missing": anchor_missing}

    distinguish_missing = [
        task
        for task in ("neighbor-distinction", "grammar-collocation", "misuse-diagnosis")
        if count_events(events, task) < 1
    ]
    audits["distinguish"] = {"complete": not distinguish_missing, "missing": distinguish_missing}

    controlled_missing: list[str] = []
    if count_events(events, "controlled-use") < 3:
        controlled_missing.append("controlled-use-count")
    if len(contexts(events, "controlled-use")) < 3:
        controlled_missing.append("controlled-use-contexts")
    # Production may be demonstrated through either live speech or typed text.
    # The goals identify preferred real-world channels; they do not duplicate
    # the same language-use gate when both are selected.
    audits["controlled-production"] = {"complete": not controlled_missing, "missing": controlled_missing}

    hidden = passed(events, "hidden-retrieval")
    hidden_dates = {event_date(event) for event in hidden if event_date(event) is not None}
    lexical_missing: list[str] = []
    if len(hidden) < 2:
        lexical_missing.append("hidden-retrieval-count")
    if len(hidden_dates) < 2:
        lexical_missing.append("hidden-retrieval-delayed-days")
    if voice_required(state, "hidden-retrieval"):
        if not direct_passed(events, "hidden-retrieval"):
            lexical_missing.append("direct-hidden-retrieval")
        if not voice_passed(events, "hidden-retrieval"):
            lexical_missing.append("voice-hidden-retrieval")
    audits["lexical-access"] = {"complete": not lexical_missing, "missing": lexical_missing}

    integration_missing: list[str] = []
    if voice_required(state, "integration-speech"):
        integration_events = voice_passed(events, "integration-speech")
        if not integration_events:
            integration_missing.append("voice-integration-speech")
    else:
        integration_events = passed(events, "integration-speech") + passed(events, "integration-writing")
    if not integration_events:
        integration_missing.append("integration-response")
    if count_events(events, "delayed-definition") < 1:
        integration_missing.append("delayed-definition")
    if not any(bool(event.get("novel_context")) for event in integration_events):
        integration_missing.append("integration-novel-context")
    audits["integration"] = {"complete": not integration_missing, "missing": integration_missing}
    return audits


def derive_progress(state: dict[str, Any], ledger: dict[str, Any], today: date) -> dict[str, Any]:
    goals = normalize_goals(state.get("goals"))
    try:
        started = date.fromisoformat(str(state.get("cohort_start")))
    except ValueError as error:
        raise SchemaError("Activation State has an invalid cohort_start") from error
    calendar_day = max(1, (today - started).days + 1)
    events = [event for event in ledger.get("events", []) if isinstance(event, dict)]
    policy = voice_policy(state)
    if state.get("status") == "pronunciation-only":
        complete = not voice_required(state, "pronunciation") or bool(voice_passed(events, "pronunciation"))
        missing = [] if complete else ["voice-pronunciation"]
        today_events = [event for event in events if event_date(event) == today]
        voice_events = [event for event in events if event.get("evidence_quality") == "voice-report"]
        return {
            "profile": "pronunciation-only",
            "calendar_day": calendar_day,
            "current_phase": "pronunciation-complete" if complete else "anchor",
            "next_phase": "pronunciation-complete",
            "unlocks_on": None,
            "completed_phases": ["pronunciation"] if complete else [],
            "phase_audit": {"pronunciation": {"complete": complete, "missing": missing}},
            "missing": missing,
            "tasks": [] if complete else ["pronunciation"],
            "task_labels": [] if complete else [TASK_LABELS["pronunciation"]],
            "voice_tasks": [] if complete else ["pronunciation"],
            "voice_due": not complete,
            "voice_policy": policy,
            "evidence_count": len(events),
            "today_evidence_count": len(today_events),
            "voice_evidence_count": len(voice_events),
            "ready_for_decision": False,
        }

    audits = phase_audit(events, goals, state)
    earliest_incomplete = next((phase for phase in PHASES if not audits[phase]["complete"]), None)
    completed = PHASES[: PHASES.index(earliest_incomplete)] if earliest_incomplete else list(PHASES)

    if earliest_incomplete is None:
        if calendar_day >= PHASE_MIN_DAY["decision-ready"]:
            current_phase = "decision-ready"
            missing: list[str] = []
            unlocks_on = None
        else:
            current_phase = "spacing-hold"
            missing = []
            unlocks_on = (started + timedelta(days=PHASE_MIN_DAY["decision-ready"] - 1)).isoformat()
    elif calendar_day < PHASE_MIN_DAY[earliest_incomplete]:
        current_phase = "spacing-hold"
        missing = list(audits[earliest_incomplete]["missing"])
        unlocks_on = (started + timedelta(days=PHASE_MIN_DAY[earliest_incomplete] - 1)).isoformat()
    else:
        current_phase = earliest_incomplete
        missing = list(audits[earliest_incomplete]["missing"])
        unlocks_on = None

    today_events = [event for event in events if event_date(event) == today]
    if earliest_incomplete is None and current_phase == "decision-ready" and any(
        TASK_PHASE.get(str(event.get("task"))) == "integration" and event.get("result") == "pass"
        for event in today_events
    ):
        current_phase = "spacing-hold"
        unlocks_on = (today + timedelta(days=1)).isoformat()
    if earliest_incomplete and current_phase == earliest_incomplete:
        earliest_index = PHASES.index(earliest_incomplete)
        advanced_today = any(
            TASK_PHASE.get(str(event.get("task"))) in PHASES
            and PHASES.index(TASK_PHASE[str(event.get("task"))]) < earliest_index
            for event in today_events
            if event.get("result") == "pass"
        )
        hidden_today = earliest_incomplete == "lexical-access" and any(
            event.get("task") == "hidden-retrieval" and event.get("result") == "pass"
            for event in today_events
        )
        hidden_dates = {
            event_date(event)
            for event in passed(events, "hidden-retrieval")
            if event_date(event) is not None
        }
        if advanced_today or (hidden_today and len(hidden_dates) < 2):
            current_phase = "spacing-hold"
            unlocks_on = (today + timedelta(days=1)).isoformat()
    voice_events = [event for event in events if event.get("evidence_quality") == "voice-report"]
    requirement_to_task = {
        "controlled-use-count": "controlled-use",
        "controlled-use-contexts": "controlled-use",
        "hidden-retrieval-count": "hidden-retrieval",
        "hidden-retrieval-delayed-days": "hidden-retrieval",
        "direct-hidden-retrieval": "hidden-retrieval",
        "voice-hidden-retrieval": "hidden-retrieval",
        "voice-pronunciation": "pronunciation",
        "voice-integration-speech": "integration-speech",
        "integration-response": "integration-speech" if "speech" in goals else "integration-writing",
        "integration-novel-context": "integration-speech" if "speech" in goals else "integration-writing",
    }
    tasks = list(dict.fromkeys(requirement_to_task.get(requirement, requirement) for requirement in missing))
    voice_tasks: list[str] = []
    if current_phase != "spacing-hold":
        if "voice-pronunciation" in missing:
            voice_tasks.append("pronunciation")
        if "voice-hidden-retrieval" in missing and "direct-hidden-retrieval" not in missing:
            voice_tasks.append("hidden-retrieval")
        if "voice-integration-speech" in missing:
            voice_tasks.append("integration-speech")
    return {
        "profile": "activation",
        "calendar_day": calendar_day,
        "current_phase": current_phase,
        "next_phase": earliest_incomplete or "decision-ready",
        "unlocks_on": unlocks_on,
        "completed_phases": completed,
        "phase_audit": audits,
        "missing": missing,
        "tasks": tasks,
        "task_labels": [TASK_LABELS.get(task, task) for task in tasks],
        "voice_tasks": voice_tasks,
        "voice_due": bool(voice_tasks),
        "voice_policy": policy,
        "evidence_count": len(events),
        "today_evidence_count": len(today_events),
        "voice_evidence_count": len(voice_events),
        "ready_for_decision": current_phase == "decision-ready",
    }


def update_derived_state(
    state: dict[str, Any],
    ledger: dict[str, Any],
    today: date,
    last_events: list[dict[str, Any]],
) -> dict[str, Any]:
    progress = derive_progress(state, ledger, today)
    previous_phase = state.get("current_phase")
    current_phase = progress["current_phase"]
    state["schema"] = STATE_SCHEMA
    state["goals"] = normalize_goals(state.get("goals"))
    state["current_phase"] = current_phase
    state["completed_phases"] = progress["completed_phases"]
    if previous_phase != current_phase:
        state["phase_started"] = today.isoformat()
    if last_events:
        latest = max(str(event.get("occurred_at", "")) for event in last_events)
        state["last_evidence_at"] = latest
        state["last_session"] = {
            "date": latest[:10],
            "source": last_events[-1].get("source"),
            "event_ids": [event["id"] for event in last_events],
        }
    return state


def deck_role(deck_name: str) -> str:
    if deck_name == USAGE_DECK or deck_name.startswith(USAGE_DECK + "::"):
        return "usage"
    if deck_name == SUPPORT_DECK or deck_name.startswith(SUPPORT_DECK + "::"):
        return "support"
    if deck_name == INBOX_DECK or deck_name.startswith(INBOX_DECK + "::"):
        return "inbox"
    return "recognition"


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return normalized or "item"


def quote_search(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def find_master_note(client: AnkiConnect, sense_id: str) -> dict[str, Any]:
    query = f'deck:"{MASTER_DECK}" tag:vocab::id::{slug(sense_id)}'
    note_ids = client.call("findNotes", query=query) or []
    if not note_ids:
        note_ids = client.call("findNotes", query=f'deck:"{MASTER_DECK}" "{quote_search(sense_id)}"') or []
    notes = client.call("notesInfo", notes=note_ids) if note_ids else []
    exact = [
        note
        for note in notes
        if note.get("modelName") == MODEL and field(note, "Sense ID") == sense_id
    ]
    if len(exact) != 1:
        raise AnkiError(f"expected one master note for {sense_id}; found {len(exact)}")
    return exact[0]
