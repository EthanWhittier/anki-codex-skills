# Anki learning stack for Codex

An integrated, local-first system for building, inspecting, analyzing, grading, and reviewing Anki decks through Codex, Anki MCP, and AnkiConnect.

## Included components

| Component | Purpose |
| --- | --- |
| `skills/` | Four Codex skills for card creation, collection inspection, deck analysis, and live chat review. |
| `local-review-stack/` | A reproducible ticketed-review stack with maintained AnkiConnect and Anki MCP source snapshots, tests, build scripts, and rollback tooling. |
| `assets/` | Positive and negative examples of the review experience. |

## Included skills

| Skill | Purpose |
| --- | --- |
| `add-anki-cards` | Design, quality-check, add, and verify cards. |
| `inspect-anki` | Inspect decks, note types, fields, cards, and notes safely. |
| `analyze-anki-deck` | Analyze a deck's cards, statistics, formulation, and scheduling. |
| `chat-anki-review` | Run an interactive review session in Codex and schedule each answer only after you choose a rating. |
| `learn-vocabulary` | Develop and manage vocabulary through a complete Anki learning lifecycle. |

## Requirements

- [Anki](https://apps.ankiweb.net/) installed locally
- Node.js 20.19 or newer for the Anki MCP server
- Python 3 for installation and verification scripts
- Codex with these skills installed
- The included maintained AnkiConnect and Anki MCP sources for ticketed chat review, or stock AnkiConnect for the legacy path

The skills never write directly to Anki's database. Anki changes go through Anki MCP or AnkiConnect, and destructive or modifying actions require explicit authorization.

## Philosophy: understanding first, retrieval always

Traditional flashcards are excellent at one important job: repeatedly retrieving a stable answer at the right time. They become less effective when a complex idea is compressed into a long answer, when wording is mistaken for understanding, or when success on one memorized example creates the illusion that a transferable skill has been learned.

These skills keep Anki's scheduling strength while broadening what a review can test. The guiding ideas are:

- **Learn before memorizing.** An unresolved explanation should be clarified before it becomes a permanent card.
- **One identifiable learning target per card.** A card can test a fact, distinction, mechanism, diagnosis, application, or transfer—not an accidental bundle of all of them.
- **Grade meaning rather than wording.** Correct paraphrases and equivalent representations should pass; missing meaning-bearing facts should not.
- **Make the prompt define the contract.** The learner should never be graded on details the question did not request.
- **Vary practice when variation is the skill.** Generated exercises can change the structure of a problem while preserving a frozen learning target, difficulty, verification method, and grading standard.
- **Keep the learner in control.** Codex may judge an answer, but only the learner's explicit Again, Hard, Good, or Easy choice changes Anki's schedule.
- **Treat misses as evidence.** Lapses can reveal a missing prerequisite, a weak distinction, an overloaded card, or genuinely difficult material; they are not automatically a failure of effort.

### What this adds beyond a conventional flashcard workflow

The system supports three complementary forms of practice:

1. **Fixed-answer cards** for stable facts, labels, rules, and narrow distinctions.
2. **Fixed open-response cards** when one stable prompt admits several independently verifiable correct answers.
3. **Generated-problem cards** when the learner should solve fresh instances instead of remembering the surface details of one example.

Together, these allow a deck to train recall and also probe explanation, comparison, error diagnosis, application, synthesis, and transfer. Chat review can accept a sound answer expressed in the learner's own words, give a concise reason for the grade, handle card media, and immediately continue through Anki's live learning and relearning queues. Deck analysis adds another feedback loop by connecting scheduling signals with the actual formulation of observed cards.

The gain is not “AI instead of flashcards.” It is a hybrid: Anki remains the source of truth for cards and scheduling, while Codex helps author better prompts, validate richer responses, generate controlled practice, and diagnose why a card is difficult.

### Expect a slower pace

This flow is intentionally slower than rapidly flipping through conventional flashcards. The learner has to produce an answer, Codex evaluates its meaning, the reference or targeted feedback is revealed, and the learner explicitly chooses the scheduling rating. Open responses and generated problems take even longer because they demand explanation, construction, or transfer rather than recognition alone.

That slower pace is a feature when the goal is deliberate practice: fewer prompts can produce richer evidence about what the learner understands, where the reasoning broke down, and whether knowledge transfers to a new case. It is still a real tradeoff. If the goal is maximum cards per minute, quick recognition, or high-volume rehearsal of stable facts, this workflow may not be the right fit. Use ordinary Anki review for those sessions, or reserve chat review for the smaller subset of cards that benefits from deeper grading.

### Traditional flashcards still have a place

Not every card should be open-ended or generative. Conventional fixed-answer and image-based cards are often the clearest and most efficient choice when the target really is stable recall or recognition. Anatomy, geography, vocabulary, symbols, dates, formulas, and visual identification are strong examples: identifying a bone on an image or recalling a country's capital usually benefits from a consistent target and an unambiguous answer.

Even in anatomy or geography, richer cards can be added selectively—for example, distinguishing commonly confused structures, explaining how location relates to function, or comparing neighboring regions. Those cards should supplement the clean recognition cards, not replace them. The right card type follows the learning target.

## Why the source is modified

This repository does more than configure stock projects. The chat-review workflow crosses three layers—Codex, Anki MCP, and AnkiConnect—and reliable scheduling requires those layers to share one protocol.

### AnkiConnect: preserve Anki's scheduler state

The original card-ID review path can race Anki's live queue. A learning card may become due after another card is presented, so a later generic `answerCards` call can fail with `not at top of queue` or act against queue state that differs from presentation time.

The maintained AnkiConnect derivative adds a ticketed chat-review protocol. When it presents a card, it keeps the pending card and the exact `SchedulingStates` returned by Anki's scheduler inside Anki. When the learner rates that card, AnkiConnect passes the original card and frozen states back through Anki's own `build_answer()` and `answer_card()` methods. The integration never calculates intervals, due dates, stability, difficulty, or retrievability itself.

Tickets also provide:

- exactly one review-log entry during normal retries;
- idempotent replay when the same ticket and rating are submitted again;
- an explicit conflict when a consumed ticket is reused with a different rating;
- one active review session per profile, preventing competing chat sessions;
- explicit errors for stale cards, collection changes, profile changes, and unverified Anki versions;
- recovery and safe abandonment without silently scheduling a card.

### Anki MCP: make rating and continuation atomic

The maintained MCP derivative adds `get_next_due_card`, `rate_card_and_get_next`, active-review status, recovery, and abandonment tools. It transports the opaque session ID and ticket without exposing them in learner-facing text. Rating and fetching the scheduler-selected next card happen as one operation, which keeps learning and relearning cards aligned with Anki's live queue.

It retains a bounded legacy path for stock AnkiConnect, but a ticket-capable installation fails closed when its exact Anki version has not passed the compatibility gate. It does not silently fall back to generic card-ID scheduling after an ambiguous ticketed failure.

### Chat-review skill: keep authority with the learner

The skill caches the ticket with the currently displayed card, requires an explicit learner rating, passes the ticket exactly once, and replaces its state atomically with the returned next card. It never treats the model's `Good` or `Again` judgment as scheduling permission. Recovery rules prevent a lost conversation state or transport error from becoming a duplicate or guessed review.

Some note types include an optional field named `AI Grader Instructions`, `Grader Notes`, or similar. That field is plain note metadata, not a dependency on the removed AI grader add-on. Codex may use it to define required facts, accepted alternatives, or common material errors during chat grading. AnkiConnect and the MCP simply transport the field with the note. Cards without grader instructions work normally from their prompt, back, and note-type contract.

### Version gates and disposable verification

Scheduler internals can change between Anki releases. The maintained stack therefore admits only exact versions listed in `versions.env` after they pass disposable tests. The gate covers new, learning, review, and relearning cards under all four ratings, queue reordering, exactly-once review logs, FSRS enabled and disabled, and a localhost-only sync round trip. It never uses a real profile or AnkiWeb credentials.

Keeping the coordinated source in one repository makes these cross-project changes reproducible, reviewable, testable, and reversible. The pinned upstream revisions and modification boundaries are recorded in [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md).

## Installation

There are two useful installation levels. Choose only what you need.

### 1. Skills only

Use this when you already have a compatible Anki MCP/AnkiConnect setup or only want the card-authoring and analysis instructions.

```sh
git clone https://github.com/EthanWhittier/anki-codex-skills.git
cd anki-codex-skills
mkdir -p ~/.codex/skills
cp -R skills/* ~/.codex/skills/
```

Restart Codex so it discovers the skills. Stock AnkiConnect can support inspection and a legacy review path, but it does not provide the maintained ticket guarantees described above.

### 2. Complete ticketed chat-review stack

This installs the maintained AnkiConnect derivative, builds the MCP server, installs the chat-review skill, and updates the `anki-mcp` entry in `~/.codex/config.toml`.

First build the source:

```sh
cd anki-codex-skills/local-review-stack
./scripts/build.sh
```

`build.sh` runs `npm ci` when dependencies are absent, type-checks and builds the MCP server, renders the tested-version compatibility manifest, and creates a packaged AnkiConnect build under `dist/`.

Next, quit Anki completely. Preview the AnkiConnect installation, then apply it:

```sh
./scripts/install-anki-connect.sh
./scripts/install-anki-connect.sh --apply
```

The installer refuses to run while Anki is open. It moves the previous AnkiConnect directory into a timestamped rollback backup before installing the maintained source. Review the installed AnkiConnect configuration afterward if you previously used a custom API key, CORS origin, bind address, or port.

Start Anki again. Then preview and apply the Codex configuration:

```sh
./scripts/configure-codex.sh
./scripts/configure-codex.sh --apply
```

The script backs up the existing Codex configuration and chat-review skill, installs the maintained skill, and points Codex at the absolute path of the newly built `main-stdio.js`.

Restart Codex completely. Existing tasks and MCP processes do not reload rebuilt JavaScript, changed skill instructions, or `config.toml` in place.

After both Anki and Codex have restarted, run the complete verification gate:

```sh
./scripts/verify.sh --live
```

This uses disposable collections and a disposable Anki base. Do not begin real-profile chat review unless verification succeeds and capability detection reports the exact running Anki version as verified.

If you prefer to configure Codex manually, the equivalent entry is:

```toml
[mcp_servers.anki-mcp]
command = "node"
args = ["/absolute/path/to/anki-codex-skills/local-review-stack/anki-mcp-server/dist/main-stdio.js"]

[mcp_servers.anki-mcp.env]
ANKI_CONNECT_URL = "http://localhost:8765"
```

### Rollback

Quit Anki, preview the rollback, and apply it only when ready:

```sh
cd local-review-stack
./scripts/rollback.sh
./scripts/rollback.sh --apply
```

Restart Anki and Codex afterward, then run a disposable verification before resuming real review. See [the local stack documentation](local-review-stack/README.md) for version upgrades, candidate-version testing, recovery semantics, and rollback selection.

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

### Positive example

The learner gives the exact semantic meaning of the formula. Codex reveals the reference answer, grades the response `Good`, gives a short reason, and waits for the learner's explicit rating. The learner chooses `4` (`Easy`), so Codex schedules it and continues.

![Positive chat-based Anki review example](assets/positive-review-example.png)

### Negative example

The learner's answer captures the broad idea of uniqueness but misreads the inner universal quantifier as existential. Codex reveals the compact reference answer and marks the response `Again`, identifying the smallest material error instead of rewarding a plausible-sounding explanation. It still waits for the learner—not the model—to choose the scheduling rating.

![Negative chat-based Anki review example](assets/negative-review-example.png)

These examples show the intended balance: accept correct meaning without requiring identical wording, but remain strict when a logical distinction changes the claim.

## Repository layout

```text
.
├── assets/
│   ├── chat-review-example.png
│   ├── negative-review-example.png
│   └── positive-review-example.png
├── local-review-stack/
│   ├── anki-connect/
│   ├── anki-mcp-server/
│   └── scripts/
├── skills/
    ├── add-anki-cards/
    ├── analyze-anki-deck/
    ├── chat-anki-review/
    └── inspect-anki/
├── SOURCE_PROVENANCE.md
└── THIRD_PARTY_NOTICES.md
```

Each skill is self-contained. Supporting references, scripts, and agent metadata live alongside its `SKILL.md`.

## Licensing and upstream projects

This repository is an aggregate containing original material and modified third-party projects under different licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md) before redistributing it.

- The included AnkiConnect snapshot is based on `FooSoft/anki-connect` and remains under GPL-3.0-or-later. Its license notice is retained in its source directory.
- The included Anki MCP snapshot is pinned to upstream commit `7d017e7` (v0.18.5), which was MIT-licensed at that revision. Its MIT license is retained in its source directory.
- Anki itself is not included. Anki is AGPL-3.0-or-later and is a separate prerequisite.
- The repository is unofficial and is not affiliated with or endorsed by Ankitects, the AnkiConnect maintainers, or the Anki MCP maintainers.

Publishing source on GitHub does not by itself grant a license to the original portions of this repository. A repository-wide license for the original skills, grader, scripts, documentation, and assets should be selected explicitly; the third-party subtrees remain governed by their own notices regardless of that choice.
