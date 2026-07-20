#!/usr/bin/env python3
"""Perform the exact authorized Vocabulary inbox capture-only operation."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import uuid
from datetime import date
from typing import Any


DEFAULT_URL = "http://127.0.0.1:8765"
MASTER_DECK = "Vocabulary"
INBOX_DECK = "Vocabulary::Inbox"
MODEL = "Vocabulary Sense"
EXPECTED_FIELDS = [
    "Front", "Back", "AI Grader Instructions", "Lemma", "Part of Speech", "Sense ID",
    "Pronunciation", "Authoritative Definition", "Definition Citation", "Required Components",
    "Working Gloss", "Anchor Context", "Grounding and Boundaries", "Usage", "Related Senses",
    "Source Encounter", "Learning Stage", "Activation State", "Activation Evidence",
]


class AnkiError(RuntimeError):
    pass


class AnkiConnect:
    def __init__(self, url: str, timeout: float) -> None:
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


def field(note: dict[str, Any], name: str) -> str:
    value = note.get("fields", {}).get(name, "")
    if isinstance(value, dict):
        value = value.get("value", "")
    return str(value).strip()


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return normalized or "candidate"


def quote_search(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def append_unique(existing: str, addition: str) -> str:
    addition = addition.strip()
    if not addition or addition in existing:
        return existing
    return f"{existing}\n{addition}".strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("word")
    parser.add_argument("--context", default="")
    parser.add_argument("--source", default="")
    parser.add_argument("--date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument(
        "--authorized-capture-only",
        action="store_true",
        help="Required guard: the learner explicitly requested this exact provisional inbox operation.",
    )
    args = parser.parse_args()

    word = args.word.strip()
    if not word:
        print(json.dumps({"error": "word must not be empty"}))
        return 2
    if not args.authorized_capture_only:
        print(json.dumps({"error": "refusing write without --authorized-capture-only"}))
        return 2

    client = AnkiConnect(args.url, args.timeout)
    try:
        client.call("sync")
        decks = set(client.call("deckNames") or [])
        if MASTER_DECK not in decks:
            raise AnkiError("Vocabulary deck is missing; capture-only cannot create the master system")
        model_fields = client.call("modelFieldNames", modelName=MODEL) or []
        if model_fields != EXPECTED_FIELDS:
            raise AnkiError("Vocabulary Sense fields differ from the canonical schema; no write made")

        query = f'deck:"Vocabulary" Lemma:"{quote_search(word)}"'
        note_ids = client.call("findNotes", query=query) or []
        notes = client.call("notesInfo", notes=note_ids) if note_ids else []
        exact = [note for note in notes if field(note, "Lemma").casefold() == word.casefold()]
        resolved = [note for note in exact if field(note, "Learning Stage").casefold() != "candidate"]
        if resolved:
            output = {
                "schema": "codex-vocabulary-capture/v1",
                "status": "resolved-match",
                "word": word,
                "note_ids": [int(note["noteId"]) for note in resolved],
                "message": "Existing resolved sense found; capture-only made no changes.",
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0

        context_line = args.context.strip() or "Context missing."
        source_line = args.source.strip() or "Source missing."
        encounter = f"Captured {args.date.isoformat()}. {source_line}"
        candidates = [note for note in exact if field(note, "Learning Stage").casefold() == "candidate"]

        if candidates:
            note = candidates[0]
            note_id = int(note["noteId"])
            fields = {
                "Anchor Context": append_unique(field(note, "Anchor Context"), context_line),
                "Source Encounter": append_unique(field(note, "Source Encounter"), encounter),
            }
            client.call("updateNoteFields", note={"id": note_id, "fields": fields})
            client.call("addTags", notes=[note_id], tags="vocabulary vocab::stage::candidate " + f"vocab::lemma::{slug(word)}")
            refreshed = client.call("notesInfo", notes=[note_id])[0]
            card_ids = [int(card_id) for card_id in refreshed.get("cards", [])]
            if card_ids:
                client.call("suspend", cards=card_ids)
            status = "candidate-updated"
        else:
            if INBOX_DECK not in decks:
                client.call("createDeck", deck=INBOX_DECK)
            token = uuid.uuid4().hex[:8]
            sense_id = f"{slug(word)}.unresolved.{args.date.strftime('%Y%m%d')}.{token}"
            fields = {name: "" for name in EXPECTED_FIELDS}
            fields.update(
                {
                    "Front": word,
                    "Back": "Unresolved candidate—do not review",
                    "Lemma": word,
                    "Sense ID": sense_id,
                    "Anchor Context": context_line,
                    "Source Encounter": encounter,
                    "Learning Stage": "Candidate",
                }
            )
            note_id = int(
                client.call(
                    "addNote",
                    note={
                        "deckName": INBOX_DECK,
                        "modelName": MODEL,
                        "fields": fields,
                        "tags": [
                            "vocabulary", f"vocab::lemma::{slug(word)}", f"vocab::id::{slug(sense_id)}",
                            "vocab::stage::candidate",
                        ],
                        "options": {"allowDuplicate": False},
                    },
                )
            )
            refreshed = client.call("notesInfo", notes=[note_id])[0]
            card_ids = [int(card_id) for card_id in refreshed.get("cards", [])]
            if card_ids:
                client.call("suspend", cards=card_ids)
            status = "candidate-created"

        verified_note = client.call("notesInfo", notes=[note_id])[0]
        verified_cards = client.call("cardsInfo", cards=card_ids) if card_ids else []
        if not verified_cards or not all(int(card.get("queue", 0)) == -1 for card in verified_cards):
            raise AnkiError("candidate verification failed: every generated card must be suspended")
        client.call("sync")
        output = {
            "schema": "codex-vocabulary-capture/v1",
            "status": status,
            "word": word,
            "note_id": note_id,
            "card_ids": card_ids,
            "stage": field(verified_note, "Learning Stage"),
            "suspended": True,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except AnkiError as error:
        print(json.dumps({"schema": "codex-vocabulary-capture/v1", "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
