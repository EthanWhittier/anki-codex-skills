---
name: analyze-anki-deck
description: Analyze one Anki deck using a deck-specific stats export, Anki MCP read/inspect data, and SuperMemo-style formulation rules. Use when Codex should ask which deck to analyze, request/upload deck-specific Anki stats, inspect existing cards/notes, identify what is going well, recommend edits to existing cards, propose new support cards, and optionally apply safe Anki MCP edits/additions without direct database writes.
---

# Analyze Anki Deck

Use this skill for per-deck learning-system analysis, not broad collection cleanup. The goal is to improve the deck the user is actively studying while respecting that the deck may be incomplete.

## Required Inputs

If missing, ask for these before doing deep analysis:

1. The exact Anki deck name to analyze.
2. A deck-specific Anki stats export or screenshot/PDF for that deck.

Do not substitute whole-collection stats when the user asked for per-deck analysis unless they explicitly approve.

## Core Workflow

1. Use Anki MCP by default.
   - If `mcp__anki_mcp__` tools are not visible, use `tool_search` for `anki mcp listDecks deckStats get_cards get_due_cards findNotes notesInfo cardsInfo addNotes updateNoteFields`.
   - If Anki MCP is still unavailable, follow the MCP startup/recovery checklist below.
   - Use `scripts/ankiconnect.py` only as a read-only fallback when MCP is unavailable or lacks a needed read/detail operation.

2. Sync and inspect deck names:
   - Call `sync` once before reading card data when the tool is available.
   - Call `listDecks(includeStats=true)` and fuzzy-match the requested deck name against real deck names.
   - Use the exact deck name from Anki for all subsequent reads.
   - Ask only when multiple deck names are genuinely plausible.

3. Read deck-specific counts and card sets. Prefer MCP tools in this order:
   - `deckStats(deck=<deck>)` for deck-level counts and interval/ease summaries.
   - `get_cards(deck_name=<deck>, card_state="new")` for new cards.
   - `get_due_cards(deck_name=<deck>, include_learning=true, include_new=true)` for currently available review, learning/relearning, and visible new cards.
   - Search-capable tools such as `findNotes`, `notesInfo`, `cardsInfo`, or `get_cards` when exposed, for lapsed/high-rep/young/mature samples.
   - If MCP does not expose search/card-detail tools needed for lapse analysis, use the fallback AnkiConnect helper script for read-only `findCards`, `cardsInfo`, and `notesInfo`.

Fallback read-only commands:

```sh
python3 ~/.codex/skills/analyze-anki-deck/scripts/ankiconnect.py deckNames
python3 ~/.codex/skills/analyze-anki-deck/scripts/ankiconnect.py findCards '{"query":"deck:\"DECK NAME\""}'
python3 ~/.codex/skills/analyze-anki-deck/scripts/ankiconnect.py findCards '{"query":"deck:\"DECK NAME\" is:new"}'
python3 ~/.codex/skills/analyze-anki-deck/scripts/ankiconnect.py findCards '{"query":"deck:\"DECK NAME\" is:due"}'
python3 ~/.codex/skills/analyze-anki-deck/scripts/ankiconnect.py findCards '{"query":"deck:\"DECK NAME\" prop:lapses>0"}'
```

4. Sample enough cards to see patterns. Prefer a mix of:
   - newest cards
   - due cards
   - young cards
   - mature cards
   - cards with lapses or low ease when available
   - cards with long answers
   - cards with non-empty grader instructions

5. Parse the stats export for:
   - reviews/day
   - time/card
   - Again rate
   - young/mature retention
   - card counts
   - new/learning/review balance
   - interval/stability/difficulty/retrievability signals when FSRS is enabled
   - due burden and backlog

6. Analyze card formulation using `references/formulation-rules.md`.
7. Analyze scheduling, lapses, retention, and FSRS signals using `references/scheduling-analysis.md`.

8. Report in this order:
   - Current deck health and caveats
   - What is going well
   - Main card-formulation risks
   - Specific existing-card edits
   - Specific cards to add
   - FSRS/scheduling implications
   - Optional safe next steps

## MCP Startup / Recovery

Codex should start Anki MCP automatically from `~/.codex/config.toml`.

Expected local server config:

```toml
[mcp_servers.anki-mcp]
command = "node"
args = ["/Users/ethanwhittier/Documents/Code/anki-ai-grader-addon/local-mcp/anki-mcp-server/dist/main-stdio.js"]

[mcp_servers.anki-mcp.env]
ANKI_CONNECT_URL = "http://localhost:8765"
```

If MCP tools are missing, stale, or returning connection errors:

1. Ask the user to make sure Anki is open and AnkiConnect is installed/enabled.
2. Verify AnkiConnect if shell access is useful:

```sh
curl -s http://localhost:8765
```

Expected response contains `AnkiConnect v.6`.

3. Ask the user to restart Codex so it respawns the MCP server from config.
4. If old npm-backed MCP processes may still be running, stop only those:

```sh
pkill -TERM -f "npm exec @ankimcp/anki-mcp-server --stdio"
pkill -TERM -f "/node_modules/.bin/ankimcp --stdio"
```

5. If the local MCP build is missing or stale:

```sh
cd /Users/ethanwhittier/Documents/Code/anki-ai-grader-addon/local-mcp/anki-mcp-server
npm install
npm run build
```

Do not run a long-lived manual stdio server for normal analysis; Codex starts the server. Manual runs are only for smoke tests.

## Important Analysis Constraints

- Do not criticize a deck for missing topics outside its current scope. The deck may be incomplete by design.
- Recommend missing cards only when they support or repair concepts already present in the deck.
- Prefer editing real observed cards over generic advice.
- For low retention, distinguish hard material from bad formulation.
- Do not optimize FSRS from tiny samples; describe uncertainty when young/mature counts are small.
- Treat lapses as diagnostic leads, not automatic proof that a card is bad.
- Recommend FSRS parameter changes only when the stats are deck-specific and the evidence is strong; usually prefer card edits and new supporting cards first.
- Use the minimum information principle: split overloaded cards into smaller, easier-to-schedule cards.
- For visual decks, recommend image recognition, image-to-name, name-to-key-feature, and confusion-set cards.
- For conceptual decks, recommend definitions plus examples, non-examples, mechanisms, and counterexamples.
- For AI-graded decks, inspect `AI Grader Instructions` and recommend stricter or more permissive notes where appropriate.

## Support Card Quality Rules

Use support cards to make the original target card easier to retrieve, not to replace it or add unrelated burden.

- Keep the real target card clean when the user wants unaided recall; put scaffolding in separate support cards or a support subdeck.
- A support hook should reduce cognitive load. Do not introduce a second obscure fact, place, term, or person unless it is already familiar to the user or is itself the useful distinction being trained.
- Prefer hooks that point directly back to the answer: etymology, distinctive location, visual contrast, spelling/sound cue, stable semantic cue, or an explicit confusion-set distinction.
- If no honest mnemonic exists, say so and use a small drill card instead of inventing a fake hook.
- Avoid vague hooks like "this is the big/old/important one" unless that cue uniquely identifies the answer.
- For arbitrary pairs, support cards can train a fixed sound/spelling pair, but they should be clearly labeled as drills rather than explanations.
- After creating support cards, audit them for unknown dependencies: if the learner would ask "what is that?", rewrite the card.

## Safe Anki MCP Rules

- Do not write directly to `collection.anki2`, `prefs21.db`, WAL files, or media databases.
- Use Anki MCP for reads and writes whenever available.
- Read first: `sync`, `listDecks`, `deckStats`, `get_cards`, `get_due_cards`, `findNotes`, `notesInfo`, `cardsInfo`, `modelNames`, `modelFieldNames`.
- Treat `addNote`, `addNotes`, `updateNoteFields`, tagging, suspending, deleting, deck moves, and `rate_card` as collection modifications.
- Confirm at action time before modifying Anki unless the user explicitly asked for the exact change.
- Add or edit in small batches, then verify returned note/card IDs.
- Never print secrets or API keys from add-on config.
- Use the fallback AnkiConnect helper script only when Anki MCP lacks the read/detail operation needed for analysis.

## Applying Improvements

When the user asks to apply recommendations:

1. Inspect the target note type fields.
2. Prepare a small batch.
3. Explain exactly what will be added or edited.
4. Ask for confirmation if the exact change was not already requested.
5. Use Anki MCP `addNotes` or `updateNoteFields`.
6. Verify with `notesInfo`.

For the user's observed AI-graded cards, a common note type is:

```text
modelName: Flashcards Rescue
fields: Front, Back, AI Grader Instructions
```

Do not assume all decks use this model; inspect first.
