# Anki Schema and Operations

Read this file before using Anki for the vocabulary system.

## Canonical structure

- Master deck: `Vocabulary`
- Candidate subdeck: `Vocabulary::Inbox` — create only when the learner approves persistent deferred capture.
- Usage subdeck: `Vocabulary::Usage` — create only when the first active blueprint is approved.
- Support subdeck: `Vocabulary::Support` — create only when the first repair card is approved.

Use Anki MCP or AnkiConnect only. Routine sync is standing-authorized: run it without asking before reads and after successful writes. If sync requires a full-upload/full-download decision, reports a conflict or authentication failure, or returns an unexpected error, stop and tell the learner; do not select a potentially destructive resolution. Never access `collection.anki2` directly.

## Master note type

Model: `Vocabulary Sense`

Expected fields in order:

1. `Front`
2. `Back`
3. `AI Grader Instructions`
4. `Lemma`
5. `Part of Speech`
6. `Sense ID`
7. `Pronunciation`
8. `Authoritative Definition`
9. `Definition Citation`
10. `Required Components`
11. `Working Gloss`
12. `Anchor Context`
13. `Grounding and Boundaries`
14. `Usage`
15. `Related Senses`
16. `Source Encounter`
17. `Learning Stage`
18. `Activation State`
19. `Activation Evidence`

The template should create one `Sense Recognition` card. Its front presents `Front`. Its back presents the compact `Back`, then the authoritative definition and citation, with the larger grounding and usage packet available as secondary reference.

Store material spelling, inflection, stress, or derivative information in `Usage` unless the established model has an approved dedicated field. Store IPA, dialect labels, and any authorized Anki audio reference in `Pronunciation`.

The model is AI-grader-compatible because it has `Front`, `Back`, and `AI Grader Instructions`. Keep `Back` as the smallest grading anchor; do not make the learner reproduce every metadata field.

Keep `Activation State` and `Activation Evidence` hidden from card templates. Store only versioned JSON defined in `activation-evidence.md`; never put raw voice transcripts or sensitive learner responses in these fields. A pending Voice entry may temporarily retain its exact generated coaching packet for recovery, but never a learner response; remove it after ingestion, cancellation, replacement, or expiry. Candidate and non-active notes may leave both fields empty. Initialize both fields when a sense enters activation.

An approved pronunciation-only recognition item may also initialize both fields while retaining `Learning Stage = Recognition` and its recognition stage tag. Use `Activation State.status = pronunciation-only`, `goals = [speech]`, required Voice policy, and an empty evidence ledger. It must not inherit the rest of the activation cohort gates. Configure or override this state only through `scripts/configure_voice_policy.py` with its authorization guard.

If the model is missing or fields differ, inspect existing models and tell the learner. Do not silently create or migrate a model. Use `add-anki-cards` to propose and obtain approval for setup changes.

For the approved 19-field activation-ledger migration, use `scripts/migrate_activation_schema.py`. It may append the two fields and initialize active notes only with `--authorized-schema-migration`. A field addition forces Anki's one-way full-sync safeguard: the script must first complete a normal sync, then verify the local migration without attempting a final normal sync. Stop and obtain the learner's explicit choice before using Anki's Sync button and choosing Upload to preserve the verified local migration. Never choose Upload or Download on the learner's behalf.

## Role-specific notes

- Use the master `Vocabulary Sense` note for one stable recognition target.
- Use `Codex Generative Exercise` in `Vocabulary::Usage` for approved active-use or transfer blueprints.
- Use `Flashcards Rescue` in `Vocabulary::Support` for narrow distinctions, cloze-like lexical access, usage judgments, or repairs.
- Link every role note through a stable sense tag and the master note's `Sense ID`.
- Add at most one initial usage blueprint and one diagnosed support card per sense unless the learner approves more.

## Tags

Use lowercase Anki hierarchy tags:

- `vocabulary`
- `vocab::lemma::<lemma-slug>`
- `vocab::id::<sense-id-slug>`
- `vocab::stage::candidate`
- `vocab::stage::recognition`
- `vocab::stage::precision`
- `vocab::stage::activation`
- `vocab::stage::integration`
- `vocab::stage::maintenance`
- `vocab::stage::retired`
- `vocab::cohort::<yyyy-mm-dd>`
- `vocab::error::wrong-sense`
- `vocab::error::definition`
- `vocab::error::lexical-access`
- `vocab::error::collocation`
- `vocab::error::grammar-frame`
- `vocab::error::register`
- `vocab::evidence::spoken::<yyyy-mm>`
- `vocab::evidence::written::<yyyy-mm>`
- `vocab::evidence::spontaneous::<yyyy-mm>`
- `vocab::pilot` while the system is being validated

Convert `qualify.v.statement` to the tag-safe slug `qualify-v-statement`. Use `Sense ID` as the canonical identity when legacy tags differ.

Keep exactly one current stage tag on the master note. Update `Learning Stage` and the stage tag together after promotion. Tolerate legacy combined values such as `recognition + precision`; normalize them only during an authorized edit.

Before adding tags, call `getTags` and reuse the established hierarchy. Before changing a stage, inspect the current note and use both `removeTags` and `addTags` if available.

Evidence tags record only coarse type and month. Add them only for verified or clearly learner-reported evidence, with approval. Do not put private sentence content into tags.

The master fields hold the detailed non-sensitive activation ledger. Completing a practice response or pasting a requested Voice bridge report authorizes the matching metadata append only when `Activation State.recording_authorized` is true. Use `scripts/record_evidence.py`; stage changes and all other writes remain separately controlled.

## Durable candidate inbox

Use this only when the learner wants to save a candidate without completing onboarding:

1. Build a provisional `Vocabulary Sense` note containing at minimum the observed form. Add the full encounter, source, reason, and capture date when supplied; explicitly label missing context/source. Use `Learning Stage = Candidate`, a provisional collision-resistant `Sense ID` containing `.unresolved.`, and `Back = Unresolved candidate—do not review`.
2. Add it to `Vocabulary::Inbox` with `vocab::stage::candidate` and the provisional ID tag.
3. Immediately suspend every generated card and verify suspension so nothing unresolved can enter reviews.
4. During onboarding, inspect the candidate, resolve the selected sense, replace provisional identity and semantic fields before any review, move the card to `Vocabulary`, replace the stage/ID tags, and unsuspend only after the learner approves the finished recognition card.
5. If one encounter contains multiple useful senses, preserve the original candidate and create separate resolved master notes only when each sense is actually learned.

Do not treat a suspended candidate as a learned item or include it in retention statistics.

A clear imperative such as `Capture only: WORD — optional context/source`, `Inbox this: WORD`, or “save this word for later” authorizes this candidate write, duplicate check, creation of `Vocabulary::Inbox` when missing, suspension, verification, and sync without a separate preview. It does not authorize a new note type, model migration, definition research, onboarding, promotion, or any other card change. Merge a new encounter into an existing unresolved candidate when safe; if a resolved sense already exists, report it without editing the resolved note.

### Manual Anki capture

The learner may add a candidate directly in Anki:

1. Select deck `Vocabulary::Inbox` and note type `Vocabulary Sense`.
2. Fill `Front` and `Lemma` with the observed word or phrase; place a sentence in `Anchor Context` and source/date in `Source Encounter` when available.
3. Set `Back` to `Unresolved candidate—do not review` and `Learning Stage` to `Candidate`.
4. Add `vocab::stage::candidate` when convenient, then suspend the generated card immediately.

On every candidate scan, inspect all notes in `Vocabulary::Inbox`, including manually added notes with missing provisional IDs or tags. Treat them as candidates, report any active unsuspended card immediately, and propose schema normalization before onboarding; do not silently discard an imperfect manual capture.

## Read workflow

1. Sync without requesting permission.
2. List decks and models when setup is uncertain.
3. Use `modelFieldNames` before the first note operation in a session.
4. Find the master note by exact `Sense ID`, stable ID tag, or lemma plus deck.
5. Use `notesInfo` for fields/tags and card-detail tools for scheduling evidence.
6. Inspect linked usage/support notes by the same stable ID tag.
7. Inspect every note in `Vocabulary::Inbox` when selecting or auditing candidates, including manually captured notes with incomplete tags.
8. Avoid dumping raw HTML or entire collections to the learner.
9. Parse Activation State and Activation Evidence for active senses; recompute mastery gates rather than advancing from elapsed days alone.

## Write workflow

1. Complete and verify the semantic packet.
2. State the approved card budget and exact intended change.
3. Check duplicates within `Vocabulary`, preferably by `Sense ID` and lemma.
4. Inspect target model fields.
5. Use Anki MCP `addNote`, `addNotes`, or `updateNoteFields`; never direct database writes.
6. Add or change tags only as part of the approved lifecycle action.
7. Verify returned IDs with `notesInfo` and inspect rendered cards when templates or rich HTML changed.
8. Sync after verification without requesting separate permission.
9. For activation evidence, use the guarded evidence script, verify event IDs and derived state, and avoid raw transcript storage.

Treat every creation, field update, tag change, suspension, move, rating, and deletion as a collection modification. Do not rate a card outside a learner-controlled review.

## Master recognition formulation

Front pattern:

> In the sentence below, what does *TARGET FORM* mean? State the relevant change, relationship, or function.

Back pattern:

> One concise, semantically sufficient answer for the selected sense.

Grader instructions should specify:

- required meaning-bearing components;
- accepted ordinary-language equivalents;
- the main sibling-sense or neighboring-concept confusion to reject;
- whether an example, exact wording, pronunciation, or formal term is optional.

Do not require details hidden only in metadata.
