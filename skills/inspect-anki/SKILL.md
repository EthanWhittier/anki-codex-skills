---
name: inspect-anki
description: Safely read, inspect, summarize, and lightly manage Anki decks, cards, notes, note types, fields, tags, and scheduling metadata through AnkiConnect. Use when Codex needs to inspect an Anki collection, sample cards from a deck, count cards/notes, examine note fields, verify newly added notes, or add notes through AnkiConnect; avoid direct collection.anki2 database writes.
---

# Inspect Anki

Use AnkiConnect at `http://127.0.0.1:8765` as the primary interface. Prefer the bundled helper script for repeatable calls:

```sh
python3 ~/.codex/skills/inspect-anki/scripts/ankiconnect.py version
python3 ~/.codex/skills/inspect-anki/scripts/ankiconnect.py deckNames
python3 ~/.codex/skills/inspect-anki/scripts/ankiconnect.py findCards '{"query":"deck:\"World Flags\""}'
```

If the sandbox cannot reach AnkiConnect, rerun the same command with escalation. This is local HTTP access to Anki, not internet access.

## Safety Rules

- Do not write directly to `collection.anki2`, `prefs21.db`, WAL files, or Anki media databases.
- Use read actions first: `version`, `deckNames`, `modelNames`, `findCards`, `findNotes`, `cardsInfo`, `notesInfo`, `modelFieldNames`, `getDeckStats`.
- Before adding or changing notes, inspect the target deck, note type, and fields.
- Treat `addNote`, `addNotes`, `updateNoteFields`, tag changes, card suspension, deletion, and deck changes as modifying the user's Anki collection. Confirm at action time unless the user explicitly asked for the exact change.
- Never print secrets. If inspecting saved add-on config, avoid echoing API keys or tokens.
- Prefer small batches first, then verify with `notesInfo` or `cardsInfo`.

## Inspection Workflow

1. Check AnkiConnect:

```sh
python3 ~/.codex/skills/inspect-anki/scripts/ankiconnect.py version
```

2. List decks and note types:

```sh
python3 ~/.codex/skills/inspect-anki/scripts/ankiconnect.py deckNames
python3 ~/.codex/skills/inspect-anki/scripts/ankiconnect.py modelNames
```

3. Find cards or notes:

```sh
python3 ~/.codex/skills/inspect-anki/scripts/ankiconnect.py findCards '{"query":"deck:\"World Flags\""}'
python3 ~/.codex/skills/inspect-anki/scripts/ankiconnect.py findNotes '{"query":"deck:\"World Flags\" tag:nordic"}'
```

4. Read a small sample:

```sh
python3 ~/.codex/skills/inspect-anki/scripts/ankiconnect.py cardsInfo '{"cards":[1777096797271]}'
python3 ~/.codex/skills/inspect-anki/scripts/ankiconnect.py notesInfo '{"notes":[1777861748245]}'
```

5. Summarize only the relevant fields. For user-facing summaries, avoid dumping huge HTML answers unless needed.

## Adding Notes

Use `addNotes` through AnkiConnect, not direct database writes. For the user's `World Flags` deck observed in this project:

```text
deckName: World Flags
modelName: Flashcards Rescue
fields: Front, Back, AI Grader Instructions
```

Example payload:

```json
{
  "notes": [
    {
      "deckName": "World Flags",
      "modelName": "Flashcards Rescue",
      "fields": {
        "Front": "Distinguish the flags of Norway and Iceland.",
        "Back": "Norway has a red field with a blue Nordic cross outlined in white. Iceland has a blue field with a red Nordic cross outlined in white.",
        "AI Grader Instructions": "Require the learner to distinguish the field colors: Norway red, Iceland blue. Exact proportions are not required."
      },
      "tags": ["world-flags", "nordic", "distinction"]
    }
  ]
}
```

After adding, verify the returned note IDs:

```sh
python3 ~/.codex/skills/inspect-anki/scripts/ankiconnect.py notesInfo '{"notes":[RETURNED_NOTE_ID]}'
```

## Useful AnkiConnect Actions

- `version`: verify AnkiConnect is running.
- `deckNames`: list decks.
- `modelNames`: list note types.
- `modelFieldNames`: inspect fields for a note type.
- `findCards`: get card IDs for an Anki search query.
- `findNotes`: get note IDs for an Anki search query.
- `cardsInfo`: inspect cards, fields, scheduling state, intervals, and deck.
- `notesInfo`: inspect note fields, tags, model, and generated cards.
- `getDeckStats`: inspect deck counts.
- `addNotes`: add a batch of notes.
- `updateNoteFields`: update fields on an existing note.

