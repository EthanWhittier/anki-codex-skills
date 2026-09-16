---
name: chat-anki-review
description: Review fixed-answer, fixed open-response, and generated-problem Anki cards in chat through Anki MCP. Use when the user wants to study, review, drill, or grade due/new cards from a named deck, including rubric-only open responses and versioned generative blueprints with frozen grading criteria and user-controlled scheduling.
---

# Chat Anki Review

Use Anki MCP as the live Anki interface and run a focused review session in chat. The user supplies a deck name; start reviewing without extra setup questions unless the deck is missing or ambiguous.

## Required Tools

Prefer the `mcp__anki_mcp__` tools:

- `sync`
- `get_next_due_card`
- `rate_card_and_get_next`
- `resume_active_review`
- `get_active_review_status` and `abandon_active_review` for diagnosis or explicitly confirmed abandonment
- `get_due_cards` or `get_cards` only for bulk inspection or fallback
- `present_card` or `rate_card` only as fallback
- `retrieveMediaFile` for cards with images
- `listDecks` when the deck name is unclear

If the tools are unavailable, use the startup/recovery checklist below instead of improvising another review path.

## MCP Startup / Recovery

Codex should start the Anki MCP server automatically from `~/.codex/config.toml`.

Expected local server config:

```toml
[mcp_servers.anki-mcp]
command = "node"
args = ["/absolute/path/to/anki-codex-skills/local-review-stack/anki-mcp-server/dist/main-stdio.js"]

[mcp_servers.anki-mcp.env]
ANKI_CONNECT_URL = "http://localhost:8765"
```

If Anki MCP tools are missing or stale:

1. Ask the user to make sure Anki is open and AnkiConnect responds at `http://localhost:8765`.
2. Ask the user to restart Codex so it respawns the MCP server from config.
3. If old npm-backed servers may be running, stop only those processes:

```sh
pkill -TERM -f "npm exec @ankimcp/anki-mcp-server --stdio"
pkill -TERM -f "/node_modules/.bin/ankimcp --stdio"
```

4. If the local build is missing or stale:

```sh
cd /absolute/path/to/anki-codex-skills/local-review-stack/anki-mcp-server
npm install
npm run build
```

Do not run a long-lived manual stdio server for the actual chat session; Codex owns the stdio process. A manual run is only for smoke testing.

## Session Start

1. Call `sync`.
2. Resolve the deck name:
   - Call `listDecks(includeStats=false)` before fetching cards.
   - Fuzzy-match the user's deck phrase against available deck names, including parent/child segments.
   - Prefer exact case-insensitive matches, then substring matches, then clear fuzzy matches.
   - If one deck is the obvious intended target, use it silently.
   - If multiple decks are plausible, ask one concise clarification with the top matches.
   - If no deck is plausible, show a short list of likely deck names and ask for the deck.
3. Fetch cards:
   - Treat "study" or "review" as any card Anki exposes in the deck-browser queues: review due, learning/relearning, and currently allowed new cards.
   - Default to `get_next_due_card(deck_name=<deck>, include_learning=true, include_new=true)`.
   - Cache the returned `reviewSessionId` and `reviewTicket` with the current card. Treat both as opaque machine state: never quote, summarize, log, or display them to the learner.
   - If the result code is `REVIEW_RECOVERY_AVAILABLE`, say `The previous local review is still pending. Resume it?` and wait for explicit permission. Then call `resume_active_review(confirm_resume=true, deck_name=<deck>, expected_card_id=<current card id when known>)`; do not start a competing session.
   - The local MCP server gates deck-scoped new cards with Anki's visible `getDeckStats` counts and sorts by scheduler `due`; `include_new=true` should not bypass daily new-card limits.
   - If the tool returns `card: null`, say `No available cards.` and stop.
   - Do not use `get_cards(card_state="new")`, unscoped new-card searches, or any custom search to bypass daily new-card limits unless the user explicitly asks to study all new/unseen cards.
   - If the user explicitly asks for all new/unseen cards regardless of Anki's visible queue, state `Bypassing visible new-card limit.` and then fetch new cards.
4. Select the review mode:
   - Use generated-problem mode only when `modelName` is exactly `Codex Generative Exercise` and `front` contains `Schema: codex-generative-exercise/v1`.
   - Use fixed open-response mode only when `modelName` is exactly `Codex Generative Exercise` and `front` contains `Schema: codex-open-response-exercise/v1`.
   - Otherwise use the ordinary fixed-answer flow: keep `back` hidden until after the user answers. If `front` has numbered or ordered subparts, freeze the full card and show the shared setup plus Part 1 instead of displaying every task at once.

## Generative Exercise Mode

Treat the generative card's `front` as an exercise blueprint and its `back` as a generation and grading contract. Never display either field verbatim as the learner's problem.

Before showing anything to the learner:

1. Parse the blueprint and contract, including the learning target, task family, prerequisites, source boundary, variation dimensions, exercise scope, review protocol, difficulty, constraints, required answer form, verification method, correctness conditions, part-specific criteria, accepted equivalents, and material errors.
2. Generate one fresh concrete problem within those boundaries.
3. Independently solve the generated problem.
4. Create an instance-specific rubric containing the required conclusion, part-specific criteria when applicable, required reasoning, accepted equivalents, and material errors.
5. Validate the instance:
   - It tests the declared focused capability or coherent extended synthesis at the requested difficulty.
   - It varies structure along declared dimensions rather than merely swapping names or labels.
   - It is self-contained, unambiguous, and supplies all assumptions and conventions that affect the answer.
   - It introduces no prerequisite or rule outside the blueprint.
   - Its decisive facts are available without simply announcing the answer, unless the blueprint explicitly requests a calibration-level cue.
   - Any non-target inference, calculation, or interpretation is transparent and independently verified so it does not become a competing source of difficulty.
   - The independently produced solution actually solves the visible problem.
   - The visible task requests every element the rubric will require.
   - The verification method succeeds.
6. If any check fails, discard the entire instance and generate another before presentation.
7. Freeze the exact problem, reference solution, and instance-specific rubric in the current review state. Never revise them after seeing the learner's response.
8. Show only the generated problem and wait for the learner's answer. If it has ordered subparts, use the stepwise protocol below and begin with Part 1.

When recent instances from the same blueprint are available in the current conversation, vary the declared structural dimensions and outcome when the contract permits; reject a candidate that repeats their underlying structure with only cosmetic substitutions. Do not invent a source or verification result that was not actually available.

After the learner answers:

1. If the instance has ordered subparts, follow the stepwise protocol below; do not reveal or grade the full solution after Part 1.
2. Otherwise reveal the frozen instance-specific reference solution as the Markdown blockquote; do not reveal the blueprint or generic contract.
3. Grade against the frozen rubric and the blueprint contract. Accept explicitly permitted equivalent reasoning and representations.
4. Use the same `✅ Good` / `❌ Again`, short-reason, user-rating, and scheduling flow as ordinary cards.
5. If genuine ambiguity escaped validation, disclose it instead of changing the solution or rubric. Do not fail an answer solely on an ambiguous element.
6. Rate the underlying blueprint card only after the user supplies the rating.

If a generated-problem card reappears after rating, including during relearning, generate and freeze a new instance before presenting it. Use this flow only for the exact generated-problem model-and-schema match; fixed open-response cards use the separate flow below.

## Fixed Open-Response Mode

Treat the Front as hidden metadata containing one exact `Visible prompt:` and the Back as a rubric-only contract. Never display either field verbatim.

Before showing the prompt:

1. Parse the visible prompt, learning target, answer freedom, source boundary, exercise scope, review protocol, correctness conditions, part-specific criteria, required reasoning, accepted alternatives, material errors, and direct validation method.
2. Confirm that the prompt requests every required element and that the validation method can check the learner's own response directly.
3. Freeze the stored prompt and grading contract in the current review state. Never add, remove, or reinterpret criteria after seeing the learner's answer.
4. When solvability is not already transparent, privately construct one valid response and verify it. Treat it only as a non-exhaustive check, never as the reference answer.
5. Show only the exact text under `Visible prompt:` and wait for the learner's answer. If it has ordered subparts, show the shared setup and Part 1 first.

After the learner answers:

1. If the prompt has ordered subparts, follow the stepwise protocol below; do not validate or grade later parts after Part 1.
2. Otherwise apply the frozen direct validation method to the learner's actual response. Do not grade by resemblance to a private exemplar.
3. Create a concise learner-specific evaluation stating the relevant verified facts or the smallest material failure. Reveal that evaluation as the Markdown blockquote; do not reveal the generic contract.
4. Accept every response satisfying the frozen criteria, including different examples, labels, representations, or reasoning explicitly allowed by the contract.
5. Describe evidential gaps precisely: say a required condition was not established or was underspecified rather than asserting its opposite unless the response supports that stronger claim. Do not equate a non-enumerated set with an infinite set.
6. Use the same `✅ Good` / `❌ Again`, short-reason, user-rating, and scheduling flow as other cards.
7. If the prompt or contract is genuinely ambiguous, disclose it and do not fail an answer solely on that ambiguity.

If an open-response card reappears after rating, present the same visible prompt with the same frozen stored contract. A new learner response may use a different valid construction; never imply that a previous or private example is uniquely correct.

## Multi-Part and Extended Exercises

Treat any prompt with numbered or explicitly ordered subparts as stepwise by default, across ordinary, open-response, and generated cards. Use whole-response mode only when the learner explicitly requests it.

1. Freeze the complete problem, solution or validation contract, and part-specific criteria before showing Part 1.
2. Cache the shared setup, ordered parts, active part, accepted parts, corrected parts, and any answers the learner supplied early.
3. Show the shared setup once, then show only `Part 1 of N`. After that, show only the current part unless earlier context is needed.
4. Evaluate only the active part. Never grade an answer against later parts that have not yet been asked.
5. When correct, say `Part N accepted.` and present the next part. Do not reveal the full answer, issue the overall grade, ask for a rating, or schedule the card yet.
6. When materially wrong, give the smallest current-part correction or explanation, mark that part as corrected, and invite a retry or continuation. Preserve the frozen later parts.
7. If the learner answers several parts at once, retain and evaluate those answers in order; do not treat unasked or omitted later parts as errors.
8. After the final part or an explicit stop, reveal a concise complete solution or evaluation, issue one overall `✅ Good` or `❌ Again`, and ask for the learner's rating. Base the recommendation on the meaning-bearing work across the parts, while leaving scheduling to the learner.
9. If the card reappears, restart at Part 1; for a generative blueprint, generate and freeze a fresh instance first.

If the learner asks for teaching during a step, explain the concept normally without rating or losing the exact active part, then resume that same part when they are ready.

## Omitted Requested Components

Before revealing the answer or issuing a grade, distinguish an omitted requested component from an incorrect answer.

1. If the learner correctly addresses part of an unnumbered compound prompt or the current active part but leaves one or more explicitly requested, separately answerable components unaddressed, preserve the response and ask one concise targeted follow-up for only the missing component. Do not reveal its answer or issue a grade yet.
2. Combine the original response with the follow-up as one attempt. If the learner supplies the missing component correctly and the combined response satisfies the frozen criteria, issue `✅ Good`; never issue `❌ Again` solely because the component was omitted initially.
3. If the follow-up is wrong, remains materially incomplete, is declined, or the learner asks to stop or be marked wrong, reveal and grade normally. Use `❌ Again` when the combined attempt still misses a material requirement.
4. Do not use this completion opportunity to erase a substantive error or contradiction already present in the response. A correct but differently worded answer is not an error.
5. For numbered or explicitly ordered subparts, continue to use the stepwise protocol. Apply this section within the current active part when that part itself requests multiple components.

Example: if the prompt asks for both a formula and an explanation, and the formula is correct but the explanation is absent, ask the learner to identify what expresses each requested idea. If that follow-up is correct, pass the card.

## Review Loop

For a multi-part card, the section above replaces the ordinary reveal-and-grade cycle until all parts are finished or the learner explicitly stops.

For each card:

1. Show only the question/prompt. Keep formatting compact.
2. Wait for the user's answer.
3. Apply **Omitted Requested Components**. When a targeted follow-up is required, wait for it before revealing or grading; otherwise continue.
4. Reveal the appropriate answer/evaluation: for an ordinary card, use the cached `back`; for a generated-problem card, use the frozen instance-specific solution; for an open-response card, generate a learner-specific evaluation from the frozen contract. Keep hidden metadata and contracts hidden.
5. Grade strictly for conceptual correctness.
6. Reply with:
   - `✅ Good` when correct enough to pass.
   - `❌ Again` when wrong, incomplete, ambiguous, off-topic, materially imprecise, empty, or unusable.
   - Always show the revealed answer or learner-specific evaluation before the grade as a Markdown blockquote.
   - Always include one short reason, including for `✅ Good`.
   - Put a blank line between the grade line and the reason.
   - Keep the reason under 25 words and focused on the answer, not the learner.
   - Do not give a lecture, explanation, mnemonic, or tangent unless the user asks.
7. Ask for rating confirmation in a compact form:
   - `` `1` Again · `2` Hard · `3` Good · `4` Easy ``
   - Only a user-supplied rating value (`1`, `2`, `3`, `4`, or an unambiguous word: `again`, `hard`, `good`, `easy`) counts as confirmation.
   - A standalone `1`, `2`, `3`, `4`, `again`, `hard`, `good`, or `easy` sent after the rating prompt is final authorization to schedule the card.
   - After receiving an explicit rating, call `rate_card_and_get_next` immediately. Do not ask "Submit this card as..." or request a second confirmation.
   - If the same message includes `skip`, `edit`, `refine`, or equivalent feedback, add the card ID and feedback to a session edit list before scheduling the explicit rating. `skip 4` means record an edit signal and submit Easy; `skip` without a rating records the signal but still requires `Rating?`.
   - Do not treat `ok`, `next`, `yes`, Enter-like acknowledgements, or silence as permission to rate.
   - If the user says `next` without a rating, ask `Rating?` instead of scheduling the card.
   - Use the user's rating, not the suggested grade, when calling `rate_card_and_get_next`.
8. Call `rate_card_and_get_next(card_id=<current card id>, rating=<confirmed rating>, deck_name=<deck>, include_learning=true, include_new=true, review_session_id=<cached reviewSessionId>, review_ticket=<cached reviewTicket>)`. Pass the opaque inputs whenever they were returned; use the legacy card-ID form only when both cached values are null.
9. If it returns `nextCard`, atomically replace the cached review state with the returned `reviewSessionId` and `reviewTicket`, then select its mode using the exact model-and-schema test. For an ordinary card, cache `nextCard.back` and inspect `nextCard.front` for ordered subparts before showing it. For a generated-problem card, complete the full generate, solve, validate, and freeze sequence. For an open-response card, parse and freeze its prompt and contract. Then show the whole prompt for a single-part card or the shared setup plus Part 1 for a multi-part card, with no transition sentence.
10. If it returns `nextCard: null`, end the session.
11. Continue until the user explicitly stops or Anki reports no available cards.

Never schedule a card before the user confirms or overrides the rating.
Never schedule from the model's own recommendation alone.

If the learner-visible current card remains in conversation but its opaque machine state is missing, call `resume_active_review` before attempting any rating. Pass the current card ID as `expected_card_id` whenever it is known and verify that the recovered card matches the frozen prompt, answer/contract, mode, and active part. If the learner's explicit `1`-`4` rating is the current message and the recovered card is an exact match, submit it once through the recovered ticket without asking again. If the match cannot be established, do not schedule; present the recovered prompt and collect a fresh answer/rating as appropriate. Never expose recovery hashes, session IDs, or tickets.

If a ticketed call reports `REVIEW_TICKET_UNKNOWN` or a transport failure, do not retry by card ID and do not guess whether the rating committed. Reconcile with `resume_active_review` using the expected card ID; the durable registry deliberately remains intact for ambiguous outcomes. If Anki definitively reports `REVIEW_TICKET_EXPIRED`, `REVIEW_COLLECTION_CHANGED`, or `REVIEW_PROFILE_CHANGED`, say `The active review state is no longer valid; refetching safely.`, discard the cached card/ticket/session, and call `get_next_due_card` without a prior session ID. Never call a ticket merely expired unless Anki returned `REVIEW_TICKET_EXPIRED`.

If Anki reports `REVIEW_SESSION_BUSY`, first use `get_active_review_status` for non-secret diagnosis. Resume only through `resume_active_review` when durable state matches. If no recoverable state exists, offer `abandon_active_review` as a last resort and call it only after the learner explicitly confirms abandonment and the expected card matches; abandonment must never schedule the card. Restarting Anki remains the fallback if safe abandonment is unavailable.

If capability detection or any ticketed call reports `ANKI_VERSION_UNVERIFIED`, stop the review immediately. Say `This Anki version has not passed the isolated review compatibility gate.` Do not call `answerCards`, do not retry by card ID, and do not tell the user to add the version to the allowlist; require the documented disposable FSRS upgrade gate first.

Do not keep a local card batch during review. Fetch one card, rate it with `rate_card_and_get_next`, then continue from the returned `nextCard`. Learning/relearning cards can re-enter the queue after rating, and singular refetching keeps the chat aligned with Anki's live scheduler.

Do not summarize between cards.

## Strict Grading Policy

Use this skill's policy, adapted from but independent of the AI typed-answer grader add-on. Changes here do not require changing the add-on prompt.

- Judge meaning, not wording overlap.
- Treat the reference answer as strong evidence about the intended answer, not a required transcript.
- Accept correct paraphrases, equivalent terminology, common abbreviations, harmless formatting differences, and minor spelling errors when meaning is clear.
- Be strict about required meaning-bearing facts.
- After the targeted completion opportunity, mark `Again` for missing material facts, contradictions, vague answers, category-level answers where specificity is required, non-answers, or answers that do not address the prompt.
- If the combined original response and targeted follow-up are still not complete enough to pass, mark `Again`.
- In stepwise mode, completeness means completeness for the active part only; never require later parts early.
- Distinguish conceptual errors from harmless notation or presentation slips. If the intended meaning is clear and an omitted domain, variable declaration, or symbol is already supplied by the prompt, prefer a brief correction over `Again`.
- Treat a missing or corrupted symbol caused by chat rendering as a tool failure, not a learner error. Retract any grade based on it and show a copyable version.
- For terminology cards, accept a nearby informal label only if it clearly gives the required role or relation and the card is not explicitly testing the formal term.
- Do not require examples, textbook phrasing, or unnecessary precision unless the prompt asks for them.
- If images are required but not available in chat, grade conservatively and say the image was unavailable only if that affects grading.

## Learner-Facing Problem Presentation

- Prefer copyable Unicode in code spans for logic and mathematics on mobile: `∀`, `∃`, `→`, `∧`, `∨`, `¬`, `∈`, `∣`, and `∤`. Do not rely solely on math rendering for a meaning-bearing symbol.
- Verify that every quantifier, connective, relation, and negation is visibly present before asking the question.
- For generated identification or classification tasks, do not bold, quote, label, or otherwise emphasize the answer-bearing expression.
- Separate headings such as `Given`, `Constraints`, and `Your task` when roles could be confused. Use direct verbs such as `Invent`, `Classify`, `Prove`, or `Explain`.
- Do not silently shorten a prompt and then grade against the original full rubric. Freeze and grade the exact learner-visible active prompt.

## Media Handling

Cards may contain images, audio, or other Anki media.

- When `present_card` returns rendered media or media references that are visible in chat, include them as part of the question/back.
- If front or back HTML contains `<img src="FILENAME">`, proactively display each image in the learner-facing card message.
- Prefer a Markdown link to the original local Anki media file when it is available (for example, in the active profile's `collection.media` directory); do not copy it merely to render it.
- Otherwise, use `retrieveMediaFile(filename=FILENAME)` for image files such as `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, and `.svg`. If it returns base64 data, save it to `/private/tmp/anki-mcp-media/FILENAME` and render that file with Markdown.
- Do not rely on an internal image-display tool call alone: the final learner-facing card message itself must contain the Markdown image reference.
- Show front-side images with the question before the user answers. Show back-side images with the revealed back before grading.
- Strip large raw HTML/CSS from the user-visible card text; preserve meaningful field labels and text.
- If image media still cannot be rendered or inspected, say `Media unavailable.` and do not grade visual recall as correct unless the text alone is sufficient.
- For audio cards, do not pretend to hear unavailable audio. Ask the user to transcribe/describe it or review that card in Anki if audio is essential.
- Keep media notes terse; do not add extra explanation unless the user asks.

## Tone

Keep the review flow non-conversational by default. The session should feel like rapid flashcard review with visible answer keys, not tutoring.

Allowed review responses:

```md
> Symmetric allows aRb and bRa. Antisymmetric says if both happen, then a = b.

✅ **Good**

Captured the bidirectional case and same-value constraint.

`1` Again · `2` Hard · `3` Good · `4` Easy
```

```md
> \(\forall a,b \in A, aRb \implies bRa\)

❌ **Again**

Missing the required reversal from aRb to bRa.

`1` Again · `2` Hard · `3` Good · `4` Easy
```

If the user breaks away to ask for an explanation, answer normally, then resume the current card when they are ready.

## Session End

When `get_next_due_card` confirms the queue is empty or the user says they are done, call `sync` again and give the shortest useful summary:

```text
Done. Reviewed N cards.
```

Include ratings only if useful or asked. If the session edit list is nonempty, include the affected card IDs and captured feedback even when the user rated them Easy. Do not add other recurring-issue commentary unless there was a clear repeated miss. Do not create new cards or edit notes unless the user explicitly asks.
