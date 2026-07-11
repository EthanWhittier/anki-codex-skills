# Anki skills for Codex

Four Codex skills for building, inspecting, analyzing, and reviewing Anki decks through Anki MCP or AnkiConnect.

## Included skills

| Skill | Purpose |
| --- | --- |
| `add-anki-cards` | Design, quality-check, add, and verify cards. |
| `inspect-anki` | Inspect decks, note types, fields, cards, and notes safely. |
| `analyze-anki-deck` | Analyze a deck's cards, statistics, formulation, and scheduling. |
| `chat-anki-review` | Run an interactive review session in Codex and schedule each answer only after you choose a rating. |

## Requirements

- [Anki](https://apps.ankiweb.net/) running locally
- [AnkiConnect](https://ankiweb.net/shared/info/2055492159), using its default local endpoint (`http://127.0.0.1:8765`)
- Codex with these skills installed
- Optional: an Anki MCP server exposing the tools named in the skills

The skills never write directly to Anki's database. Anki changes go through Anki MCP or AnkiConnect, and destructive or modifying actions require explicit authorization.

## Install

Copy the skill directories into your personal Codex skills directory:

```sh
cp -R skills/* ~/.codex/skills/
```

Restart Codex so it discovers the installed skills. Keep Anki open whenever you create, inspect, analyze, or review cards.

If you use a local Anki MCP server, add its command to `~/.codex/config.toml`. Replace the placeholder with the server's real path:

```toml
[mcp_servers.anki-mcp]
command = "node"
args = ["/absolute/path/to/anki-mcp-server/dist/main-stdio.js"]

[mcp_servers.anki-mcp.env]
ANKI_CONNECT_URL = "http://localhost:8765"
```

## Create a deck and cards

Ask Codex in ordinary language. A useful initial prompt is:

> Create an Anki deck named “Discrete Mathematics”. Use Basic cards. Help me turn these notes into concise cards, show me the proposed cards first, then add and verify them after I approve.

Recommended flow:

1. Open Anki and start the request in Codex.
2. Codex inspects the available decks, note types, and field names.
3. If the deck does not exist, explicitly authorize creating it through AnkiConnect or your Anki MCP server.
4. Codex identifies the learning target, checks correctness, and proposes focused cards.
5. You approve the exact cards or explicitly authorize adding suitable cards as it goes.
6. Codex adds the notes with duplicate prevention and verifies the returned note IDs.

For conceptual material, the card-creation skill favors short, meaning-focused prompts, useful contrasts, examples, counterexamples, applications, and transfer questions. It can also create fixed open-response or generated-problem cards when the installed Anki note type supports them.

More prompt examples:

> Add cards to “Discrete Mathematics” from these notes. Preserve my wording unless a correction is required, and ask before writing to Anki.

> Inspect “World Flags”, then propose support cards for concepts that are already in the deck. Do not add anything until I approve it.

> Analyze my “Biology” deck using this deck-specific statistics export and recommend the highest-impact card edits.

## Review a deck in chat

Start with a deck name:

> Review my “Discrete Mathematics” deck.

Codex syncs Anki, resolves the deck name, and fetches one available card at a time. It shows only the question until you answer. After grading, it reveals the answer, gives a concise `Good` or `Again` judgment, and asks you to select the scheduling rating:

```text
1 Again · 2 Hard · 3 Good · 4 Easy
```

Only your explicit rating schedules the card. Codex then fetches the next card from Anki's live queue, including learning and relearning cards when they reappear. Say “done” to stop and sync.

### Example

The screenshot below shows a correct answer graded `Good`, followed by the learner selecting `4` (`Easy`) and Codex continuing the live Anki schedule.

![Chat-based Anki review example](assets/chat-review-example.png)

## Repository layout

```text
.
├── assets/
│   └── chat-review-example.png
└── skills/
    ├── add-anki-cards/
    ├── analyze-anki-deck/
    ├── chat-anki-review/
    └── inspect-anki/
```

Each skill is self-contained. Supporting references, scripts, and agent metadata live alongside its `SKILL.md`.
