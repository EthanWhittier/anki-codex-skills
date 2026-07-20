# End-to-End Operating Workflow

Use this as the system's control plane. The learner supplies interpretations, connections, examples, priorities, and real attempts. Codex owns routing, research, verification, card design, state inspection, practice selection, diagnosis, and follow-through.

## Contents

1. System bootstrap and recovery
2. Discovery and candidate capture
3. Prioritization and track choice
4. Guided sense acquisition
5. Authoring and verification
6. Recognition and precision reviews
7. Activation and integration
8. Real-world evidence
9. Repair
10. Maintenance, audit, and retirement

## 1. System bootstrap and recovery

On first use or after a long gap:

1. Clarify the long-term outcome in practical terms: reading/listening recognition, writing, speech, or a mixture.
2. Inspect the existing `Vocabulary` structure, note fields, card templates, pilot items, due load, and grader compatibility.
3. Recover each word's state from its `Sense ID`, lifecycle field, tags, linked notes, and scheduling history. Do not assume prior chat context survives.
4. Recommend the four-week calibration budget below. Lower it when reviews accumulate.
5. Establish whether approval of an exact preview authorizes the matching Anki write and verification.
6. Pilot the system with a few words and audit it before scaling.

Offer a short baseline only if the learner wants longitudinal comparison: one unseen-context recognition sample, one meaning-to-word retrieval sample, and a short natural writing or spoken response. Store it only in a learner-approved location and never treat rare-word count as the score.

Do not give a giant vocabulary placement test by default. Begin with actual encounters and expressive needs; use sampling later to calibrate difficulty.

### Four-week calibration budget

Recommend, without hard enforcement:

- unlimited candidate capture;
- about seven newly introduced recognition senses per week, with bursts of up to three in one day;
- two active sense-frames per two-week cohort;
- roughly 15–20 minutes of total vocabulary work per day.

The learner may deliberately exceed any numerical recommendation. State the likely future review or divided-attention cost once and proceed. Never relax the requirement that a review card represent a resolved, understood sense.

After four weeks, inspect backlog, actual review time, recognition relative to the FSRS target, cohort completion, and delayed target-hidden production. When evidence is healthy, recommend increasing either recognition to about ten senses per week or activation to three senses per cohort. Change one dimension at a time so the next audit remains interpretable.

### One-command daily session

For a generic “Let's study my vocab system,” “start,” or “continue” request, run the bundled `scripts/vocab_state.py` first. Do not reconstruct state from chat memory or ask the learner what kind of vocabulary work to do.

The script returns an ordered agenda from:

1. due, learning, and scheduler-available new reviews;
2. the first missing task in every active sense-frame's earliest unlocked mastery phase;
3. a cohort decision only when all gates pass and day 15 has arrived;
4. one inbox candidate when review burden and active work permit onboarding;
5. capture or discovery only when nothing scheduled remains.

Execute the full agenda in one roughly 15–20 minute session. After each activity, continue to the next automatically. Use `chat-anki-review` for live scheduling and keep Anki ratings learner-controlled. After each activation task, normalize and record the approved non-sensitive evidence through `scripts/record_evidence.py`; this makes interrupted sessions resumable without chat memory. Ask only meaning-bearing questions, review answers, or consequential choices; do not ask the learner to select a phase, remember a date, count cohort days, inspect decks, or issue a second command for activation.

If a day is missed, resume the earliest incomplete gate from durable Anki state. Do not cram missed exercises, skip ahead because time elapsed, or credit evidence that was never produced. Accept spacing holds when evidence finishes before the next minimum-day unlock.

An explicit new-word, capture-only, activation, repair, audit, or review request starts that named route directly.

## 2. Discovery and candidate capture

Accept candidates from:

- a sentence the learner read or heard;
- a familiar word used in an unfamiliar sense;
- a word the learner repeatedly misinterprets;
- an idea the learner cannot express precisely;
- learner-approved analysis of their writing or speech;
- an agent recommendation requested for a domain or communicative goal.

For every candidate, preserve the form, full encounter, source, date when known, and why it seemed worth learning. If there is no real encounter, label the context as curated.

When the learner is ready, resolve the candidate immediately. When they are not, use the approved queue. A queue item is not a learning card and must not become due. Periodically prune duplicates, already-known items, low-value curiosities, and words whose useful sense cannot be recovered.

For fast capture, accept `Capture only: WORD — optional context/source` or an equivalent imperative. Run `scripts/capture_candidate.py` with the authorization guard; do not hand-build the candidate operation. The script performs sync, duplicate checks, canonical note verification, inbox creation when needed, candidate add/update, suspension, verification, and final sync. If only the form is supplied, it marks context/source as missing for later onboarding.

At later generic starts, include the inbox count and strongest candidate in the state brief. When due review and scheduled activation are current, recommend the strongest candidate using recurrence, likely utility, expressive need, and encounter quality. Preserve deferred candidates until they are onboarded, rejected, merged as duplicates, or explicitly retired.

## 3. Prioritization and track choice

Recommend the next item using:

- probability of seeing or needing the sense again;
- whether it fills a real expressive or interpretive gap;
- value of the distinction from familiar words or sibling senses;
- usefulness of its collocations or discourse frame;
- quality of the source encounter;
- current review and activation burden;
- the learner's interest.

Choose one initial track:

- **Recognition only**: understand the selected sense in context. This is the default for most words.
- **Recognition plus precision**: understand and articulate important components or boundaries.
- **Activation candidate**: the learner genuinely wants to retrieve and use this sense in writing or speech.
- **Defer or reject**: the sense is too low-value, poorly grounded, redundant, or costly right now.

Track choice is reversible. Recognition does not obligate activation.

## 4. Guided sense acquisition

Run the onboarding sequence in `SKILL.md` and build `semantic-packet.md` one answer at a time.

The minimum viable sequence is:

1. recover the encounter;
2. elicit the learner's contextual interpretation and confidence;
3. ask one grounding or boundary question;
4. verify the exact dictionary sense and important usage facts;
5. compare source, learner gloss, and agent explanation;
6. let the learner revise or demonstrate the model;
7. choose recognition, precision, activation, defer, or reject.

Expand the interview only where uncertainty remains. Do not interrogate every packet field mechanically.

## 5. Authoring and verification

Translate the approved semantic packet into the smallest useful card set:

1. one master recognition note for the selected sense;
2. one precision prompt only when a definition component or boundary deserves retrieval;
3. one generated active-use blueprint only after activation is chosen;
4. one narrow support card only after a diagnosed failure.

Before writing:

- show substantive corrections;
- state each card's job and the total review cost;
- freeze the sense, authoritative definition, required components, and material-error rubric;
- check duplicates and existing sibling senses.

After writing, verify note/card IDs, fields, tags, rendering, deck placement, and scheduling state, then sync. A returned ID alone is not sufficient verification.

## 6. Recognition and precision reviews

Support two review modes:

### Normal Anki review

The learner reviews independently. The fixed or AI-aware card uses the stored grading contract. Later audits inspect scheduling and error patterns without pretending that a correct button press proves active use.

### Guided chat review

Use `chat-anki-review` and run one card at a time:

1. sync and fetch the actual due card;
2. show only the prompt;
3. receive the complete learner answer before revealing criteria;
4. compare against required components and accepted equivalents;
5. distinguish correct alternatives from target retrieval;
6. explain the smallest material correction;
7. ask for a corrected response when useful;
8. let the learner choose the Anki rating;
9. diagnose repeated misses before proposing an edit or support card.

For recognition, vary context while keeping the selected sense stable. For precision, test components and boundaries rather than verbatim dictionary wording unless exact wording was explicitly chosen as the target.

## 7. Activation and integration

Activation is a managed two-week cohort, not a mass conversion of recognition cards. Inspect eligible items, recommend a small cohort, obtain confirmation, create or reuse one active-use blueprint per sense, apply the cohort tag, and run the schedule in `lifecycle.md`.

Practice should move through:

1. pronunciation and visible-word rehearsal;
2. sense and near-neighbor discrimination;
3. grammatical frame and collocation;
4. controlled original sentences;
5. communicative-intent prompts with the target hidden;
6. short writing or 30–60 second speech in a novel context;
7. delayed retest and a promote/extend/repair/demote decision.

Give separate feedback on meaning, syntax, collocation, register, and discourse effect. A sentence can be grammatical yet pragmatically unnatural. Prefer a simpler familiar word when the target adds no useful precision.

Use `activation-evidence.md` to select and record the exact next task. Calendar dates unlock later phases but never complete earlier ones. An Anki Usage review may fulfill a matching activation task; record it once after rating and do not assign duplicate transient practice.

For speech-oriented work, route an explicit driving, car, hands-free, or Voice request through `voice-bridge.md`. Generate the packet from current durable state, pause the main branch, and resume after validating and recording the returned bridge report. Never perform Anki scheduling inside the Voice offshoot.

## 8. Real-world evidence

Invite, but do not force, the learner to notice:

- a new authentic encounter;
- a moment when the target came to mind but was not used;
- deliberate use in writing or speech;
- spontaneous appropriate use;
- a correction from another person or later self-correction.

Verify the relevant context before counting evidence. Record approved coarse evidence tags as defined in `anki-schema.md`; keep sensitive content out of Anki unless the learner explicitly wants it stored.

Promotion should combine delayed retrieval, varied prompts, appropriate construction/register, and real use when available. Never claim to have heard speech that was not provided as audio.

## 9. Repair

When a review or real use fails:

1. inspect the exact note, prompt, answer, and history;
2. identify whether the failure concerns sense, definition component, spelling/form, pronunciation, lexical access, grammar, collocation, register, or prompt quality;
3. reteach through one learner attempt and one focused correction;
4. edit an invalid card before adding another;
5. add at most one smallest support intervention when the master card is sound;
6. tag the error and reassess after delayed retrieval;
7. regress or suspend only when evidence justifies it.

Do not solve a meaning problem with more repetitions of the same ambiguous prompt.

## 10. Maintenance, audit, and retirement

### End of each session

- verify and sync approved writes;
- verify activation event IDs and recomputed mastery state;
- state current stage and next evidence;
- preserve unresolved questions;
- report review burden when it changed.

### Weekly

- inspect due load, candidate queue, current cohort, and repeated error tags;
- finish or repair active work before expanding the cohort;
- select the next few recognition candidates, not a giant backlog.
- compare current intake with the soft calibration budget and report overrides without treating them as violations.

### Monthly

- inspect deck-specific retention and lapse clusters;
- sample mature recognition in unseen contexts;
- sample lexical access with the target hidden;
- compare writing/speech precision and naturalness over time;
- promote, extend, demote, suspend, or retire items individually;
- change intake only after observing burden and performance.
- after the initial four weeks, change recognition or activation intake—not both in the same audit cycle.

### Long term

Optimize for accumulated durable gains, not rare-word counts. Maintain broad recognition with sparse cards and develop only a few high-value active sense-frames at a time. Retire cards that are redundant, invalid, or no longer worth their burden; prefer suspension so the record remains recoverable.
