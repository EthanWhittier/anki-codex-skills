# AI Typed Answer Grader for Anki

This is a desktop Anki add-on version of the Flashcards app's AI grading flow.
It adds an answer box to ordinary Anki review cards and grades the learner answer
with OpenAI when the answer is shown. By default it displays an `Again` or `Good`
recommendation with an accept button; `auto_apply_grade` can be enabled to answer
the card automatically.

## What It Supports

- Anki desktop add-on packaging.
- Ordinary Anki review cards using the embedded answer box.
- Native typed-answer cards using `{{type:Field}}`.
- Structured OpenAI Responses API grading.
- The same pass/fail grading policy used by the app.
- Optional deck-level instructions via add-on config.
- Optional card/note-level instructions from fields named `AI Grader Instructions`,
  `Grader Notes`, or `Notes`.

For ordinary cards, the add-on uses the rendered answer side as the reference
answer.

## One-Command Local Install

From the repository root:

```sh
python3 scripts/install_addon.py
```

This symlinks the add-on into the default Anki `addons21` folder for your
platform. On macOS, that is:

```text
~/Library/Application Support/Anki2/addons21/ai_grader/
```

Use `--copy` if you want to copy files instead of symlinking them:

```sh
python3 anki_ai_grader_addon/scripts/install_addon.py --copy
```

Restart Anki after installing.

## Special Instructions

For card-specific instructions, add a field to the note type named:

```text
AI Grader Instructions
```

Examples:

```text
Require the exact city name.
```

```text
Accept either the common name or the Latin binomial.
```

For deck-specific instructions, edit the add-on config:

```json
"deck_instructions": {
  "Biology": "Accept common abbreviations.",
  "1234567890": "Require exact spelling for vocabulary cards."
}
```

The key can be the deck name or the numeric deck id.

## Reference-Free Grading

By default, the add-on can grade cards even when there is no reference answer on
the answer side. In that case, it asks the model to grade from the prompt,
trusted grader instructions, note fields, the learner answer, and general
knowledge.

This is useful for explanation, mechanism, analogy, prediction, and failure-mode
cards where a single stored answer would be too narrow. You can disable it in the
add-on config:

```json
"allow_grading_without_reference": false
```

## Local Usage Log

The add-on writes successful grading usage to `ai_grader.log` in the active Anki
profile folder. The log is bounded with rotation: by default, each file is capped
at 256 KB and no backups are kept.

You can tune or disable this in the add-on config:

```json
"enable_local_log": true,
"local_log_max_bytes": 262144,
"local_log_backup_count": 0
```

## Manual Local Install

Copy the contents of `ai_grader` into an Anki profile add-on folder named
`ai_grader`, for example:

```text
~/Library/Application Support/Anki2/addons21/ai_grader/
```

The folder should contain `__init__.py`, `addon.py`, `openai_client.py`,
`text.py`, `config.json`, `config.schema.json`, and `manifest.json`.

Restart Anki, then open:

```text
Tools > Add-ons > AI Typed Answer Grader > Config
```

Set `openai_api_key` before reviewing typed-answer cards.

## Package As `.ankiaddon`

From this repository:

```sh
cd ai_grader
zip -r ../ai_grader.ankiaddon .
```

Then install `anki_ai_grader_addon/ai_grader.ankiaddon` through Anki's add-on
manager.

## Complete local review stack

The maintained AnkiConnect and Anki MCP sources used by the Codex chat-review workflow live under `local-review-stack/`. That directory includes its own setup, compatibility, verification, upgrade, and rollback documentation.

## Licensing

This directory contains original code plus modified upstream snapshots with separate licenses. Read the repository-level `THIRD_PARTY_NOTICES.md` and `SOURCE_PROVENANCE.md`. In particular, the maintained AnkiConnect derivative remains GPL-3.0-or-later, while the pinned Anki MCP revision included here carries its retained MIT license.
