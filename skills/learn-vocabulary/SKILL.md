---
name: learn-vocabulary
description: >-
  Manage learner-authored English vocabulary through its full Anki lifecycle: contextual
  capture, sense resolution, authoritative definition and usage checks, semantic grounding,
  minimal AI-graded notes, scheduled review, selective speech/writing activation,
  error repair, promotion, maintenance, and audits. Use for the one-command daily controller
  (“let's study my vocab system”), quick suspended-inbox capture (“capture only” or “inbox
  this”), hands-free ChatGPT Voice practice (“I’m driving,” “car mode,” or “ready for Voice”),
  or requests to discover, learn, add, activate, distinguish, review, audit, maintain, or
  retire vocabulary in the dedicated Vocabulary Anki system. Prefer this over generic
  add-anki-cards for vocabulary lifecycle work.
---

# Learn Vocabulary

Own the vocabulary workflow from first encounter to long-term use. Guide the learner; do not hand them a checklist to manage alone. Make the learner generate meaning, boundaries, connections, and uses while Codex routes the session, researches, verifies, corrects, records, schedules, reviews, repairs, promotes, and audits.

Treat this as one connected system:

`discover/capture → prioritize → resolve one sense → ground meaning → author/verify → recognize → activate selectively → integrate into speech/writing → maintain or retire`

Run diagnosis and repair from any stage. Track recognition and productive availability separately.

## Required companion skills

- Use `inspect-anki` for collection reads, note inspection, and verification.
- Use `add-anki-cards` for formulation checks and every Anki write.
- Use `chat-anki-review` when the learner asks to conduct and schedule live reviews.
- Treat routine Anki synchronization as standing-authorized; sync without requesting permission.
- Never write directly to Anki database files.

Read the relevant bundled reference before acting:

- Read [operating-workflow.md](references/operating-workflow.md) at the start of every lifecycle request. It defines setup, candidate capture, prioritization, reviews, promotion, repair, and audits.
- Read [semantic-packet.md](references/semantic-packet.md) for onboarding a word, verifying definitions, or authoring a sense record.
- Read [lifecycle.md](references/lifecycle.md) for promotion, activation cohorts, integration, maintenance, repair, or progress audits.
- Read [anki-schema.md](references/anki-schema.md) before any Anki read or write in this system.
- Read [activation-evidence.md](references/activation-evidence.md) for daily activation, mastery gates, evidence recording, interruption recovery, or cohort decisions.
- Read [voice-bridge.md](references/voice-bridge.md) for driving, car, hands-free, ChatGPT Voice, Voice prompt, or pasted Voice-report requests.

## Bundled controllers

- Resolve scripts relative to this `SKILL.md`; never assume the conversation workspace is the skill directory.
- Run `scripts/vocab_state.py` at the start of every generic daily study request. Treat its JSON agenda as the deterministic routing layer; use the companion skills to perform the work.
- Run `scripts/capture_candidate.py WORD --context CONTEXT --source SOURCE --authorized-capture-only` only after an exact capture-only imperative. The guard flag records that the user authorized only the provisional inbox operation.
- Run `scripts/record_evidence.py` after each verified in-chat activation task. For Voice, semantically review every assigned task and submit the complete report as one atomic event batch; never record its tasks one at a time. Pass only normalized, non-sensitive metadata and the matching authorization guard.
- Run `scripts/voice_prompt.py --authorized-voice-session` to generate a phase-specific, paste-ready prompt for ChatGPT Voice and durably register its session ID and fingerprint. The learner's Voice request authorizes only that session-metadata write.
- Run `scripts/validate_voice_report.py` on the pasted report before semantic review or evidence recording. It is read-only and rejects stale, mismatched, or structurally invalid reports.
- Run `scripts/manage_voice_sessions.py` with its guard after an explicit cancel request, or to remove expired Voice metadata during an authorized daily session.
- Use `scripts/migrate_activation_schema.py` only for an explicitly approved 17-to-19-field Vocabulary Sense migration. It requires a clean normal pre-sync and leaves Anki's forced one-way post-migration sync for a separately confirmed local Upload.
- If a script reports an Anki sync conflict, schema mismatch, connection error, active inbox card, or another unexpected condition, stop that route and report it. Do not improvise a write.
- The scripts own state recovery, minimum-spacing calculation, mastery-gate selection, evidence validation, duplicate checks, suspension, and verification. They do not answer prompts, choose Anki ratings, resolve senses, or make promotion decisions for the learner.

## Interaction contract

1. Ask one high-value question at a time. Do not present a long intake form.
2. Let the learner attempt the meaning, connection, distinction, or usage before teaching it.
3. Preserve the learner's correct wording in the working gloss and grounding fields.
4. Correct substantive errors explicitly and minimally. Explain what changes and why before treating the corrected idea as learned.
5. Use a support ladder when the learner is stuck: one conceptual hint, then a constrained comparison, then direct teaching.
6. Never mistake uncertainty for failure. Record confidence and revisit weak boundaries.
7. Keep dictionary wording, the learner's paraphrase, and Codex's explanation visibly distinct.
8. Do not create a review card while the underlying sense remains unresolved.
9. Recommend the next step and review load; ask the learner for meaning-bearing answers and consequential choices, not system administration.
10. Resume from durable Anki state when possible. Do not depend on chat memory for a word's stage, identity, completed activation task, or Voice result.
11. Treat elapsed time as a minimum-spacing constraint; require recorded mastery evidence before phase advancement.

## Recommended four-week calibration

Present these as starting recommendations, never hard limits:

- capture any number of candidates without activating them;
- introduce about seven resolved recognition senses per week, allowing bursts of up to three in one day;
- activate two sense-frames per two-week cohort;
- aim for roughly 15–20 minutes of total vocabulary work per day.

At the four-week audit, recommend increasing either recognition to about ten senses per week or activation to three senses per cohort when due work is current, review time remains acceptable, recognition is near the learner's FSRS target, and active words survive delayed target-hidden retrieval. Do not increase both dimensions in the same audit cycle.

These numbers are advisory. If the learner explicitly chooses more, explain the likely review/attention tradeoff once, then honor the override without repeated friction. Continue to enforce semantic resolution, card quality, duplicate prevention, and honest stage evidence.

## Begin or resume a session

1. Infer the session mode from the learner's request; do not require them to name a lifecycle stage.
2. Read `operating-workflow.md` and the mode-specific references.
3. If Anki state matters, sync without asking and inspect the relevant note, linked cards, stage, cohort, error tags, and scheduling evidence before questioning the learner.
4. Continue at the earliest unmet step. Do not repeat settled onboarding questions unless evidence shows the model is unstable.
5. Ask one question or present one review prompt at a time.
6. End by recording approved changes and stating the next evidence needed.

## One-command daily study controller

Use this controller for “Let's study my vocab system,” “study my vocabulary,” or another generic study/start/resume request. The learner intends one session per day and should not have to name phases, remember dates, request activation separately, or administer the inbox.

1. Run `scripts/vocab_state.py`. It performs the standing-authorized sync and returns setup health, live review inventory, active cohort day/phase, inbox candidates, warnings, and an ordered agenda.
2. Give a one- or two-sentence state brief. Do not ask whether a new word was encountered and do not make the learner choose the agenda.
3. Execute every agenda item in order within the roughly 15–20 minute daily budget:
   - use `chat-anki-review` for cards exposed by the live scheduler, including its user-controlled rating flow;
   - resume the first missing task in each active sense-frame's earliest unlocked phase;
   - record and verify matching non-sensitive evidence after each completed task;
   - perform a cohort decision only when the script reports `decision-ready`;
   - onboard the strongest inbox candidate only when the agenda includes it, eliciting one meaning-bearing answer at a time;
   - offer capture/discovery only when no scheduled work exists.
4. After each item, continue automatically to the next agenda item. Do not require “practice,” “continue,” or another trigger. A learner may stop or time-box the session at any point.
5. End only when the agenda is complete, the learner stops, the daily budget is reached, or a genuine blocker requires input. State what was completed and what the next daily invocation will recover.

The cohort date sets the earliest unlock for each phase; the evidence ledger controls actual advancement. If the learner misses a day, do not create catch-up work or pretend the missed evidence exists. Resume the earliest unfinished phase. When a gate finishes early, accept the script's spacing hold instead of inventing permanent reviews.

An explicit request overrides the controller. “I have a new word” starts onboarding without forcing a review detour. Capture-only imperatives use the shortcut below and return immediately.

## Route the request

### Setup or “start my system”

On true first use, audit the existing Vocabulary deck, note types, grader fields, current pilot notes, review load, and user goal. Recommend the smallest setup or migration. Establish a pilot and operating budget before bulk intake. Do not recreate working structures. On later generic starts, use the default session controller rather than repeating setup questions.

### Discovery, candidate list, or word recommendation

Capture words from real encounters, recurring confusions, expressive gaps, or learner-approved analysis of their speech/writing. Preserve the source context. Recommend priority from usefulness, recurrence, expressive value, sense clarity, and review burden—not rarity alone.

If several candidates arrive together, place them in a lightweight queue and guide one sense at a time. Use the approved durable inbox procedure in `anki-schema.md` when persistence is requested; never leave an unresolved candidate in active reviews.

### Capture-only shortcut

Recognize requests such as `Capture only: WORD — CONTEXT`, `Inbox this: WORD`, or “save this word for later.” Do not begin onboarding, browse definitions, or ask meaning questions.

Treat the imperative capture request as exact authorization for the provisional candidate operation only. Run `scripts/capture_candidate.py` with the supplied word, context, and source plus `--authorized-capture-only`; do not reimplement the operation manually. Context and source are strongly preferred but optional; the script labels missing information rather than fabricating it. If the same resolved lemma exists, report the match without editing it. Give a one-line confirmation and return to the prior activity unless the learner asks to onboard immediately.

### New word or sense

Run the guided onboarding workflow below. If the learner only wants a quick explanation, teach it without writing to Anki. If they want it captured for learning, complete the semantic packet before proposing a card.

### Existing vocabulary item

Sync and inspect the master sense note, stage, linked usage/support notes, tags, and available scheduling evidence. Resume at the earliest unmet stage rather than restarting the intake interview.

### Due reviews or “study with me”

Use `chat-anki-review`. Present the stored card without leaking the answer, receive the learner's response, grade only against the frozen contract, explain material errors, and let the learner control Anki scheduling. After a miss, diagnose before creating or editing anything. See the review loop in `operating-workflow.md`.

### Activation cohort

Read `lifecycle.md`, inspect eligible sense notes and current load, then recommend a priority set and cohort size for one confirmation. During initial calibration, recommend two sense-frames for two weeks; after a successful four-week audit, recommend three. Treat six to eight simultaneous activation items as a caution threshold rather than an absolute prohibition.

### Writing, speaking, or real-world use

Coach the learner at the current stage. For active access, start from a communicative intention with the target hidden. Check meaning, grammar, collocation, register, and discourse effect separately. Record genuine evidence only after the learner reports or demonstrates it; never infer spoken performance from typed work.

### ChatGPT Voice offshoot

For “I’m driving,” “car mode,” “ready for Voice,” or a Voice-prompt request, read `voice-bridge.md` and enforce its parked gate before running tools or displaying copyable material. Once the learner is parked, run the main state controller, generate the exact packet with `scripts/voice_prompt.py --authorized-voice-session`, present it in one copyable code block, and pause the main activation branch. Do not conduct Anki ratings or visual work in Voice.

Require setup before driving and keep moving-vehicle practice fully audio-only. Once parked, have the learner ask the same Voice conversation `Give me the bridge report`, then paste the JSON into Codex. Validate it against the frozen sense, correct material errors, preserve every assigned outcome—including fail or unverified—and record the complete report atomically as `voice-report` evidence before resuming the main flow. Never claim Codex heard the audio or that the transcript is verbatim.

When a learner pastes a `vocab-voice-bridge/v1` report without an explicit preface, infer this route immediately.

### Confusion or repeated miss

Inspect the actual card and response pattern. Diagnose wrong sense, weak definition component, lexical access, collocation, grammar frame, register, or overbroad prompting. Guide the learner through the distinction before proposing one smallest repair.

### Audit or maintenance

Inspect the candidate queue, deck-specific statistics, stage/cohort/error/evidence tags, lapse clusters, linked support cards, review burden, and user-reported real usage. Report recognition, precise understanding, deliberate production, and spontaneous availability separately. Recommend intake, promotion, repair, demotion, or retirement changes; do not infer speech integration from Anki retention alone.

## Guided onboarding workflow

### 1. Establish the encounter

Ask for the sentence, situation, speaker, or text in which the word appeared. If no encounter exists, label any example as curated rather than personal.

### 2. Elicit the learner's model

Ask what the word appears to mean in that context and how confident the learner is. Then ask one tailored grounding question, such as:

- What changed in the situation because this word applies?
- What familiar idea is closest, and what seems different?
- Give one case that clearly fits or clearly does not fit.
- What would the speaker be committing to by using this word?

Do not require all of these.

### 3. Verify the lexicographic sense

Browse an authoritative dictionary source for the exact sense and citation. Use a second authoritative source when the sense boundary, register, or grammatical behavior is uncertain. Verify important collocations or usage claims rather than inventing them from one example.

Do not reveal a dictionary answer before the learner's first attempt unless they explicitly request direct teaching or have no usable prior understanding.

### 4. Reconcile understanding

Compare the learner's model with the sourced sense. Identify what was correct, missing, or overgeneralized. Invite the learner to revise the working gloss or connection. Codex may propose wording after the learner has supplied the meaning-bearing content.

### 5. Build the semantic packet

Assemble one sense cluster using `semantic-packet.md`. Keep related senses visible but unscheduled. Never ask for or test a list of all dictionary senses. For a recognition-only item, keep usage research compact. For an activation candidate, verify pronunciation, grammatical frame, collocation, register, and a situation in which the learner would genuinely want the word.

### 6. Rehearse and test the model

Ask the learner for one fresh interpretation, boundary judgment, or personally relevant use. Correct meaning before style. If the learner cannot explain why the word fits, continue grounding instead of authoring a card.

### 7. Set the card budget

State the proposed learning priority and smallest card budget. Default to one master recognition card whose back contains the authoritative definition and expandable grounding. Add precision, active-use, or support cards only when the learner approves the role and load.

### 8. Write and verify

Before writing, show any substantive correction and the exact front/back when the learner has not already approved them. Use Anki MCP with duplicate prevention. Verify returned note and card IDs, rendered fields, tags, and note type. Sync after successful writes.

## Learning and promotion

- Treat recognition, precise explanation, lexical access, appropriate production, and spontaneous use as separate capabilities.
- Promote only learner-prioritized senses into activation. Recognition is not a promise to activate every word.
- For speech, include prompts that begin from communicative intent without displaying the target word.
- Ask the learner to say a response aloud before typing or summarizing it when audio is unavailable. Never claim to have graded unheard speech.
- Keep generated contexts variable but freeze the sourced definition, target sense, required components, and material-error rubric.
- Require evidence from delayed, varied retrieval before promotion. See `lifecycle.md` for criteria.
- Recover mastery from the activation ledger and minimum-spacing gates in `activation-evidence.md`; never advance solely because calendar days passed.
- Do not promote every recognized word. Keep a broad recognition stream and a narrow, deliberate activation stream.
- Treat real-world use as evidence, not as proof by itself: verify that the sense, construction, and register were appropriate.

## Repair policy

Use the smallest diagnosis-specific repair:

- wrong sense: pairwise distinction or contextual classification;
- missing definition component: one focused precision card;
- weak lexical access: intent-to-word cloze or scenario cue with the word hidden;
- unnatural collocation or grammar: collocation cloze or sentence repair;
- register mismatch: audience/scenario judgment;
- broad prompt: rewrite the existing card before adding support.

Do not create a full palette of cards mechanically. Do not wait for a default leech threshold when the same confusion has already appeared twice.

## Safety and authority

- The learner controls word priority, activation status, cohort size, and acceptable review burden.
- Treat note creation, edits, tags, stage changes, suspension, deck moves, rating, and deletion as writes.
- Obtain action-time confirmation unless the learner explicitly authorized the exact change or standing workflow.
- Treat routine sync as a standing exception to confirmation: run it freely before relevant reads and after verified approved writes. If sync reports a conflict, authentication failure, full-sync direction choice, or unexpected error, stop and report it rather than choosing a potentially destructive resolution.
- At initial setup, offer a standing workflow in which approval of an exact card preview authorizes the matching write and verification; do not broaden that authorization.
- Prefer demotion or suspension over deletion; delete only on an explicit request.
- Do not silently change the authoritative definition, sense ID, or frozen grading contract after reviews exist. Version a materially changed practice blueprint.
- Never bulk-add a candidate list as active cards merely because the list was supplied.
- Never refuse intake solely because a recommended numerical budget was exceeded; distinguish an advisory override from unresolved or unsafe card construction.

## Handoff pattern

End each session with:

- the current sense and lifecycle stage;
- what the learner supplied versus what was verified or corrected;
- Anki changes and verified IDs, if any;
- the next learner action or promotion evidence needed;
- current review/cohort burden when relevant;
- unresolved ambiguity or uncertainty.
