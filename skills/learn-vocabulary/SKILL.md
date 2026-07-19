---
name: learn-vocabulary
description: >-
  Guide learner-authored vocabulary development through the complete Anki lifecycle:
  capture a word in context, elicit the learner's own understanding and connections,
  verify an authoritative sense definition and current usage, build a grounded semantic
  packet, create and verify minimal AI-graded Anki notes, run selective two-week
  activation cohorts for writing and speech, diagnose sense/collocation/register errors,
  promote items through recognition, precision, activation, integration, and maintenance,
  and audit progress. Use when the user asks to start, discover, capture, prioritize, learn,
  add, activate, practice, distinguish, repair, review, audit, maintain, retire, or otherwise
  manage English vocabulary in the dedicated Vocabulary Anki system; prefer this over
  generic add-anki-cards for vocabulary lifecycle work.
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
10. Resume from durable Anki state when possible. Do not depend on chat memory for a word's stage or identity.

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

## Default “start my vocabulary system” controller

Use this controller when the learner gives a generic start/resume request without naming a word or activity:

1. Sync and inspect setup health, due recognition/usage/support cards, active cohort work, deferred candidates, and current review burden.
2. Give a compact state brief and recommend today's order; do not dump collection data.
3. Ask whether the learner has a newly encountered word or phrase to capture. If so, request the word and its sentence/situation together when available; never block quick capture because context is missing.
4. Route the next action:
   - new encounter: capture it, then recommend onboarding now or deferring it based on review load;
   - no new encounter and cards are due: begin a guided due-card review immediately;
   - no due cards but activation work is pending: begin the current cohort exercise;
   - no due work but candidates exist: recommend one candidate and begin onboarding after confirmation;
   - nothing pending: ask whether to use a learner-selected word, analyze an approved language sample, or receive one agent recommendation.
5. After completing one branch, return to the state brief and recommend the next unfinished action until the learner ends the session or reaches their review budget.

An explicit request overrides this controller. “Study my vocabulary” starts the due-review route without first asking for a new word. “I have a new word” starts capture/onboarding without forcing a review detour.

## Route the request

### Setup or “start my system”

On true first use, audit the existing Vocabulary deck, note types, grader fields, current pilot notes, review load, and user goal. Recommend the smallest setup or migration. Establish a pilot and operating budget before bulk intake. Do not recreate working structures. On later generic starts, use the default session controller rather than repeating setup questions.

### Discovery, candidate list, or word recommendation

Capture words from real encounters, recurring confusions, expressive gaps, or learner-approved analysis of their speech/writing. Preserve the source context. Recommend priority from usefulness, recurrence, expressive value, sense clarity, and review burden—not rarity alone.

If several candidates arrive together, place them in a lightweight queue and guide one sense at a time. Use the approved durable inbox procedure in `anki-schema.md` when persistence is requested; never leave an unresolved candidate in active reviews.

### Capture-only shortcut

Recognize requests such as `Capture only: WORD — CONTEXT`, `Inbox this: WORD`, or “save this word for later.” Do not begin onboarding, browse definitions, or ask meaning questions.

Treat the imperative capture request as exact authorization for the provisional candidate operation only: sync, check duplicates, create `Vocabulary::Inbox` if this is the first capture, add or update the candidate, suspend and verify every generated card, then sync. Context and source are strongly preferred but optional; label missing information rather than fabricating it. If the same resolved sense already exists, do not alter it under capture-only authority; report the match. Give a one-line confirmation and return to the prior activity unless the learner asks to onboard immediately.

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
