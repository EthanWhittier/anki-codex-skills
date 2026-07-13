# Front/Back Card Styling

These scripts update Anki note types through AnkiConnect. Anki must be running with AnkiConnect enabled.

Apply the AI Grader/Codex-inspired style to note types with `Front` and `Back` fields:

```bash
cd /absolute/path/to/anki-codex-skills/anki-ai-grader/ai_grader
node apply-codex-basic-style.mjs
```

Restore the original `Basic` style and templates from the saved backup:

```bash
cd /absolute/path/to/anki-codex-skills/anki-ai-grader/ai_grader
node restore-basic-template.mjs
```

The restore script reads:

```text
anki-basic-template-backup-2026-05-06.json
```

The apply script updates compatible front/back note type templates and styling. Python add-on UI changes still require restarting Anki.
