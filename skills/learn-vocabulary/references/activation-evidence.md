# Activation Evidence and Mastery State

Use this reference for daily activation, progress recovery, phase advancement, Voice reports, interrupted sessions, and cohort decisions.

## Contents

1. Source of truth
2. Evidence event contract
3. Mastery gates
4. Spacing and resumption
5. Recording workflow
6. Promotion and audits

## 1. Source of truth

Store activation configuration and derived status in the master note's `Activation State` field using `vocab-activation-state/v1`. Store append-only, non-sensitive event metadata in `Activation Evidence` using `vocab-activation-evidence/v1`.

Treat the evidence ledger as the source of truth. `current_phase` and `completed_phases` in Activation State are cached summaries that `scripts/record_evidence.py` refreshes after every verified event. `scripts/vocab_state.py` recomputes progress from the ledger rather than trusting chat memory or elapsed time.

Activation State records:

- canonical Sense ID;
- speech and/or writing goals;
- cohort start;
- current derived phase and phase start;
- whether non-sensitive evidence recording has standing authorization;
- whether the Voice offshoot is enabled;
- pending Voice session IDs, fingerprints, phases, missing-requirement signatures, assigned task keys, creation/expiry times, and the exact generated packet for 48-hour recovery;
- the last recorded session event IDs.

Do not store raw voice transcripts, private situations, or long learner responses in either field. Keep only coarse contexts, task results, error classes, visibility, modality, pronunciation status, and a short evidence note.

## 2. Evidence event contract

Every event records:

- stable event ID and timestamp;
- source: `codex-chat`, `chatgpt-voice-bridge`, `real-world-report`, or `anki-review`;
- evidence quality: `direct-chat`, `voice-report`, `self-report`, or `anki-scheduling`;
- phase and canonical task key;
- speech, writing, mixed, or recognition modality;
- target visibility;
- pass, partial, fail, or unverified result;
- count and coarse context labels when multiple productions were tested;
- whether the context was novel;
- whether the target was retrieved before reveal;
- whether the target leaked early;
- whether audio was actually heard and the resulting pronunciation status;
- canonical error classes and a note of at most 300 characters.

Use `scripts/record_evidence.py` for every append. Its authorization guard, validation, duplicate prevention, state recomputation, verification, and sync are mandatory. Completing a daily practice response or pasting a requested Voice bridge report authorizes only the matching non-sensitive evidence append when Activation State records standing authorization. Record each direct-chat task after validation, but record a Voice report only as one complete atomic batch covering every assigned task. It never authorizes an Anki rating, stage change, card-content edit, raw transcript storage, promotion, or deletion.

## 3. Mastery gates

Calendar time only unlocks a phase. Advance only after all earlier gates pass.

| Phase | Earliest cohort day | Evidence required |
|---|---:|---|
| Anchor | 1 | one meaning-and-boundary pass; when speech and required Voice are enabled, one validated Voice pronunciation pass; two natural visible-target uses |
| Distinguish | 3 | one near-neighbor distinction; one grammar/collocation pass; one misuse diagnosis |
| Controlled production | 6 | three natural uses across three coarse contexts, supplied either by speech or writing |
| Lexical access | 10 | two target-hidden retrieval passes on different dates; under required Voice policy, one validated Voice pass and one non-Voice pass |
| Integration | 13 | under required Voice policy for a speech goal, one validated target-hidden 30–60 second Voice response; otherwise one spoken response or short paragraph; at least one novel context; one delayed definition-components pass |
| Decision | 15 | all gates above plus an evidence-quality review |

For a hidden-retrieval pass, require `target_visibility=hidden`, `target_retrieved_before_reveal=true`, and `target_revealed_early=false`. A correct synonym is valid language but not target retrieval.

Voice evidence may satisfy production gates when its report is coherent, structurally validated, semantically reviewed, tied to an active pending session, and Voice actually heard the response. Label it `voice-report`; never present it as a verbatim transcript. Do not promote automatically from Voice reports alone when important ambiguity remains.

Required Voice is the default for activation notes with `speech` goals and `voice_enabled=true`, including legacy notes without an explicit policy. `voice_policy=optional` keeps Voice available without source-specific gates; `voice_policy=off` disables it. `voice_waivers` may exempt one canonical Voice gate after explicit learner approval. A waiver removes the modality requirement; it never creates evidence.

A recognition note may use `status=pronunciation-only` with required Voice. It remains in Recognition, requires only a validated pronunciation event, and must not inherit the rest of the activation phase gates.

## 4. Spacing and resumption

If a gate is completed before the next phase's earliest day, enter `spacing-hold`; do not manufacture extra permanent reviews. Normal Anki reviews continue.

After one hidden-retrieval pass on the current date, hold the second pass until a different date. When delayed work completes an earlier phase, do not stack the newly exposed phase into the same daily session.

If the learner misses days, keep the earliest unfinished phase. Never skip a gate, stack catch-up exercises, or infer practice. If a session is interrupted, Anki review tickets recover scheduled cards and the evidence ledger prevents completed activation tasks from being repeated. An unrecorded partial answer may be safely repeated.

## 5. Recording workflow

After a chat exercise or validated Voice report:

1. Freeze the prompt and grading criteria before the learner responds.
2. Evaluate meaning, grammar, collocation, register, discourse effect, lexical retrieval, and pronunciation separately as applicable.
3. Explain any substantive correction before recording a pass.
4. Normalize one or more event objects without raw transcript content.
5. Run `scripts/record_evidence.py --sense-id ... --events-json ... --authorized-evidence-record`.
6. Verify the returned event IDs and recomputed progress.
7. Continue to the next unfinished agenda item automatically.

For an Anki Usage review, record the matching activation task only after the learner completes and rates the review. Do not count a Usage review and a transient exercise twice for the same work.

## 6. Promotion and audits

At the cohort decision, inspect the actual ledger, Anki history, unfamiliar contexts, error pattern, modality coverage, and evidence quality. Guide one explicit decision: promote, extend, repair, or demote. Stage and tag changes remain learner-controlled writes.

At the monthly audit, include blind probes that are not copied from stored examples:

- mature-sense recognition in an unseen context;
- target-hidden retrieval from communicative intent;
- a novel paragraph and, when relevant, spoken response;
- a judgment that a familiar simpler word is preferable when the target adds no precision.

Adjust intake from measured burden and delayed performance, not from raw card counts alone.
