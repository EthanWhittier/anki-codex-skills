# Local Ticketed Anki Review Stack

This directory is the maintained local source of truth for reliable chat review. It combines an independently versioned Anki MCP checkout, an independently versioned AnkiConnect checkout, the deployed chat-review skill source, reproducible operational scripts, and rollback backups.

The ticket protocol fixes the observed `not at top of queue` race by keeping the pending card and its frozen `SchedulingStates` inside Anki. Anki still selects every card, applies daily limits and learning priority, computes the next state, writes the review log, and returns the next scheduler-selected card. The stack does not use public GUI MCP tools, edit `collection.anki2`, or sort a database-derived queue.

## Tested versions

See `versions.env` for exact revisions, runtime paths, exact tested Anki versions, ticket protocol version, and tested FSRS modes. The release gate passed on Anki 25.09.2 and 26.05 with FSRS both enabled and disabled. Anki 26.05 uses the packaged macOS application layout, so operational tests run its bundled modules through `scripts/run-anki-python.sh`. The pre-change local median for `rate_card_and_get_next` was 125 ms across 197 logged successes; the acceptance ceiling for the ticketed median is 150 ms on this machine.

The AnkiConnect checkout is based on upstream commit `4064fa1`, with the installed Anki 25 compatibility changes imported into version control before the chat-review patch. The MCP checkout retains its nested Git repository and original commit `7d017e7`; its pre-existing dirty and untracked review work was migrated intact from `local-mcp/anki-mcp-server`.

## Build and source tests

```sh
cd /absolute/path/to/anki-codex-skills/anki-ai-grader/local-review-stack
./scripts/build.sh
./scripts/verify.sh
```

`build.sh` renders the add-on compatibility manifest from `versions.env`, then produces `anki-mcp-server/dist/main-stdio.js` and `dist/AnkiConnect-chat-review.zip`. `verify.sh` compiles the add-on, runs the headless protocol contract, reruns the frozen-state scheduler race, runs the FSRS state/rating matrix and localhost-only sync round trip, checks the installed source when present, and verifies the configured Codex and skill paths.

The mandatory scheduler proof creates a temporary `collection.anki2`, arranges learning card B to become due while card A remains presented, answers A with the states captured at presentation, asserts exactly one review entry for A, and confirms Anki returns B next. The temporary directory is destroyed. It never opens a user profile.

The FSRS gate enables FSRS in disposable collections and covers new, learning, review, and relearning cards under all four ratings. Each case replays the same ticket and requires exactly one review-log entry. It also verifies queue reordering and round-trips an FSRS-reviewed card through Anki's bundled sync client and a temporary localhost-only sync server. No AnkiWeb credentials or user profile are used.

## Install and configure

1. Build and run source verification.
2. Quit Anki. This is mandatory: Python add-on modules are loaded at process start.
3. Install the maintained add-on:

   ```sh
   ./scripts/install-anki-connect.sh --apply
   ```

   The installer moves the entire prior add-on to a timestamped backup before copying any new files. It refuses to run while Anki is active and restores the backup if copying fails.

4. Start or restart Anki. For a no-real-collection deployment test, use `./scripts/disposable-live-smoke.sh`; it launches Anki with a temporary base, copies the installed add-on into that base, creates disposable cards, verifies capability detection and idempotent replay, then destroys the base.
5. Configure Codex and install the maintained skill:

   ```sh
   ./scripts/configure-codex.sh --apply
   ```

   This backs up `~/.codex/config.toml` and the current chat-review skill, then points Codex at:

   ```text
   /absolute/path/to/anki-codex-skills/anki-ai-grader/local-review-stack/anki-mcp-server/dist/main-stdio.js
   ```

6. Restart Codex. This is mandatory: existing tasks and MCP processes do not reload `config.toml`, rebuilt JavaScript, or skill instructions in place.
7. With the restarted Codex and restarted Anki, run:

   ```sh
   ./scripts/verify.sh --live
   ```

Do not call the rollout complete before steps 4, 6, and 7 succeed.

## Review behavior

The learner-facing sequence remains question, learner answer, revealed answer/evaluation and grade, explicit learner `1`–`4` rating, exactly one scheduling operation, then the next card. `reviewSessionId` and `reviewTicket` are opaque machine-facing fields. The skill must cache and pass them but never display them.

AnkiConnect allows one active ticketed review session per profile. A second session receives `REVIEW_SESSION_BUSY`. Repeating a consumed ticket with the same rating returns the cached result and does not add a review. Repeating it with a different rating returns `REVIEW_TICKET_ALREADY_USED_DIFFERENT_RATING`. Stale, mismatched, deleted-card, collection-change, and queue-state errors are explicit and never fall back to card-ID scheduling.

At presentation, AnkiConnect copies the protobuf `SchedulingStates` produced by `get_queued_cards()` and keeps it with the ticket. At answer time it maps only the user's `1`–`4` choice to Anki's rating enum, then passes the original card and frozen states to Anki's `scheduler.build_answer()` and `scheduler.answer_card()`. The stack never calculates an interval, due date, stability, difficulty, or retrievability and never edits FSRS memory state itself.

The in-memory completed-ticket cache covers normal transport retries while Anki remains running. It does not claim crash-atomic exactly-once behavior if Anki commits and crashes before caching or returning the response.

The local `rate_card` and `rate_card_and_get_next` MCP annotations intentionally preserve the existing fast review path (`readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`). This is a semantic mismatch for scheduling, retained because the skill requires an explicit learner rating and the local environment otherwise adds per-card confirmation latency. Revisit those annotations separately before any public upstream proposal.

## Stock AnkiConnect compatibility

Capability detection reports the running Anki version, ticket protocol version, exact tested-version list, verification result, and FSRS status. It is cached per MCP process. Stock AnkiConnect falls back to the existing card-ID path. A maintained ticket-capable AnkiConnect running an unlisted Anki version instead fails closed with `ANKI_VERSION_UNVERIFIED`; neither ticket acquisition nor ticket consumption may fall back to generic `answerCards`. Only the exact legacy error text `not at top of queue` triggers containment on stock AnkiConnect: the MCP verifies that the card exists, waits 75 ms, and retries once. It does not retry unrelated application errors or generic `answerCards` transport failures. Ticketed `chatReviewAnswer` requests may be retried because the ticket makes replay idempotent.

## Upgrading Anki

Do not add a candidate release to `TESTED_ANKI_VERSIONS` merely to make review start. Use this order:

1. Back up the entire Anki profile from Anki's normal backup/export workflow and verify the backup exists. Do not use the real profile for the compatibility gate.
2. Install or unpack the candidate Anki version in isolation, with a separate launcher/runtime path. Leave `versions.env` unchanged so the deployed stack continues to reject that version.
3. Run the candidate's bundled Python against disposable collections and the localhost-only sync server:

   ```sh
   ANKI_PYTHON=/path/to/candidate/python \
   ANKI_CANDIDATE_VERSION=26.x.y \
   ./scripts/disposable-fsrs-gate.sh
   ```

   `ANKI_CANDIDATE_VERSION` is a test-process-only admission override. It is not installed and cannot enable ticketed review in Anki. A mismatch between the declared and running versions fails the test.
4. Only after the complete matrix passes, update `ANKI_VERSION`, `TESTED_ANKI_VERSIONS`, `ANKI_PYTHON`, and `ANKI_LAUNCHER` in `versions.env`. Run `./scripts/build.sh`; it renders the deployed compatibility manifest from that tested list.
5. Quit Anki, run `./scripts/install-anki-connect.sh --apply`, and restart Anki. Restart Codex after rebuilding the MCP so it loads the new JavaScript and capability cache.
6. Run `./scripts/verify.sh --live` after both restarts. Do not resume real-profile review until capability detection reports the exact running version as verified and the post-restart disposable smoke passes.

If an upgraded Anki reports `ANKI_VERSION_UNVERIFIED`, stop. Never retry by card ID and never add the version to `versions.env` before the isolated gate succeeds.

## Updating the maintained forks

Keep both nested repositories independent. Inspect their dirty state before fetching or merging:

```sh
git -C anki-mcp-server status --short --branch
git -C anki-connect status --short --branch
```

Never clean, reset, or stash automatically. After an intentional upstream update, rerun the headless protocol test, the scheduler race at least three times, MCP unit/workflow/type checks, build, isolated live smoke, and latency measurement before reinstalling.

## Rollback

Quit Anki, then preview and apply rollback:

```sh
./scripts/rollback.sh
./scripts/rollback.sh --apply
```

Rollback restores the original pre-install AnkiConnect directory and the pre-install Codex settings/skill by default, while keeping the MCP path pointed at the consolidated checkout so its stock-AnkiConnect fallback remains usable. Set `ANKI_CONNECT_BACKUP` or `CODEX_BACKUP` to select a different timestamped backup. It never opens or edits a collection. Restart Anki and Codex afterward, then run an isolated disposable smoke test before resuming real review.

## Sync

The FSRS compatibility gate proves a collection/full-upload/full-download round trip against Anki's bundled sync implementation and a temporary localhost-only server. It intentionally does not use AnkiWeb, so account authentication and remote service availability remain outside automated coverage. After the stack is verified and the user deliberately resumes a real profile, run the normal MCP `sync` action and confirm success before relying on real-deck review. Do not use test automation to open or modify the user's real collection.
