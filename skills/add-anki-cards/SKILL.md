---
name: add-anki-cards
description: Design, quality-check, refine, and add fixed-answer, fixed open-response, or generated-problem Anki cards through Anki MCP/AnkiConnect. Use for understanding-first hybrid authorship, rubric-only grading contracts, grader-aware cards, higher-order learning maps, versioned practice blueprints, verified note creation, or topic coverage tracking.
---

# Add Anki Cards

## Required Setup

Use Anki MCP or AnkiConnect for all Anki reads and writes. Do not write directly to Anki database files.

Read `references/supermemo-checklist.md` before judging whether proposed cards are well formulated.

For AI-graded note types or conceptual card/deck design, also read `references/grader-aware-design.md` before proposing, refining, or adding cards.

For generative exercise blueprints, read `references/generative-blueprints.md` completely before designing or adding one.

If the current task also requires inspecting deck structure, note fields, or existing cards, use the `inspect-anki` skill as well.

## Workflow

1. Establish the target deck and note type before adding cards.
   - Prefer the user's named deck.
   - Inspect note fields with `modelFieldNames` or equivalent before the first add.
   - Prefer the deck's existing card model unless the user specifies another.

2. Establish the learning target before finalizing a card.
   - Identify what understanding, capability, fluency, connection, or transfer the card should develop. A predicted mistake is optional, not mandatory.
   - Treat the learner as the authority on topic priority and acceptable deck load. Never infer that a topic is high value merely because it is complicated, confusable, or generative-card-friendly.
   - Before allocating a rich sequence or extended worksheet, state the proposed card budget and obtain the learner's approval of both the topic priority and batch size. If either is unclear, default to the smallest viable addition and present expansions as optional.
   - Do not turn an unresolved explanation into a memorization card. Help the user understand or refine the concept first.
   - If the user asks to review wording or understanding before creation, do not write to Anki until the exact card is approved, even when an earlier standing instruction allowed adding cards as they go.
   - Before proposing advanced cards or blueprints, consult an existing staged higher-order learning map. If none exists and advanced sequencing matters, create one organized around mechanisms, diagnosis/comparison, worked synthesis, and transfer.
   - Set a coverage budget from the learner-assigned priority, then use complexity, confusability, downstream leverage, and demonstrated errors only to decide how best to spend that budget. Do not mechanically create every card role for every topic.
   - For a simple or low-priority topic, usually prefer one strong anchor plus at most one useful contrast or application. Reserve richer definition/example/mechanism/error/transfer sequences for high-priority, complicated, or repeatedly confused concepts.

3. Parse each proposed card.
   - Preserve the user's wording unless correctness, grammar, or Anki rendering requires a small change.
   - Treat substantive wording/style rewrites as suggestions, not silent edits.
   - Normalize only harmless grammar typos when the meaning is unchanged.

4. Check correctness before formulation.
   - If the card is factually wrong, overgeneralized, ambiguous in a correctness-relevant way, or missing a key condition, do not add it.
   - Tell the user the smallest needed correction and wait for approval.
   - If the issue is merely wording preference, do not block addition.

5. Check formulation and card role.
   - Choose deliberately among atomic retrieval, a focused exercise, and an extended worksheet.
   - Prefer one clear fact, distinction, rule, or example for ordinary fixed retrieval, and prefer short answers there.
   - Do not treat atomicity as a blanket prohibition on synthesis. An extended worksheet may require substantial effort when its ordered parts form one coherent learning arc and the concept is important enough to justify the review time.
   - Reserve extended worksheets for high-leverage synthesis, transfer, or proof practice. Split when the parts are independent, when a miss cannot be localized, or when incidental bookkeeping competes with the intended learning.
   - For any numbered or ordered multi-part card, require a stepwise review protocol and part-specific grading criteria so the learner starts with Part 1 and is never graded against unasked later parts.
   - Add prerequisite cards or distinction cards when the current card depends on an unclear concept.
   - Consider definitions, distinctions, examples, non-examples, mechanisms, applications, predictions, counterexamples, error diagnoses, failure modes, and transfer/analogy cards.
   - Build coherent sequences when useful: concept, concrete example, contrast, application, failure case, and transfer.
   - Choose deliberately among a fixed-answer card, a fixed open-response card, and a generated-problem blueprint. Keep stable facts, rules, and narrow distinctions fixed-answer; use fixed open-response when one stable prompt admits many directly verifiable answers; use generated-problem when the problem itself should vary structurally.
   - Require a particular representation, enumeration, or formal construction only when producing that form is part of the learning target. Do not let incidental bookkeeping compete with the intended conceptual task.

6. Design for the AI grader when supported.
   - Make the front define the task and expected depth. Never make the grader require material the front did not ask for.
   - Use direct action verbs and visibly separate supplied facts, constraints, and learner actions. Prefer `Invent one rule. It must...` over ambiguous phrases such as `Any acceptable rule must...`.
   - Do not visually emphasize, quote, or label the answer when identification is part of the task.
   - Require comparison with an alternative only when contrast itself is the learning target. Do not append `explain why the closest alternative does not fit` as generic rigor.
   - Treat the back as the smallest sufficient grading anchor, not a transcript the learner must reproduce.
   - For ordinary AI-graded cards, choose deliberately between reference-backed and explicitly approved reference-free grading; never omit the back silently. Fixed open-response cards and generated-problem blueprints always require a Back contract.
   - Write grader instructions around required meaning-bearing facts, accepted variants, common material errors, and whether examples or symbols are optional.
   - Prefer semantic grading: accept correct paraphrases and harmless presentation differences while remaining strict about required meaning.

7. Add the card when authorized.
   - If the user has explicitly told Codex to add cards as they go, add correct and well-formulated cards without re-confirming each one.
   - Otherwise, confirm before any Anki write.
   - Use duplicate prevention when available, usually deck-scoped.

8. Verify after adding.
   - Read the returned note IDs with `notesInfo` or equivalent.
   - Report created note IDs and any skipped duplicates or failures.

9. Maintain topic coverage when requested.
   - Use a small markdown tracker under the current workspace, commonly `work/<deck>-<topic>-tracker.md`.
   - Record existing direct cards, added note IDs, covered topics, gaps, and pending correctness checks.
   - Update coverage only after the Anki note has been verified.
   - Track the approved card budget as well as conceptual gaps, so broader coverage does not silently become uncontrolled deck growth.

## Understanding-First Hybrid Authorship

For higher-order permanent cards:

1. Propose the learning purpose, card role, and a candidate front derived from that purpose.
2. Invite the learner to draft the meaning-bearing back and revise the front if desired.
3. Check reasoning before polishing wording.
4. If needed, increase support gradually: one conceptual hint, then an incomplete structure, then candidate wording only when requested or necessary.
5. Preserve the learner's wording unless correctness, grammar, or rendering requires a change.
6. Explain the smallest substantive correction and wait for exact approval before writing.

Do not force every card into a mistake-prevention framing. Mental models, fluency, synthesis, and transfer are sufficient learning purposes.

## Practice Exercise Cards

Use the shared `Codex Generative Exercise` note type. Use the exact `codex-open-response-exercise/v1` schema for a fixed prompt with a rubric-only Back, or `codex-generative-exercise/v1` when Codex must generate a fresh problem. Keep subject knowledge, source boundaries, difficulty, verification, and grading criteria inside each card rather than this skill.

Practice exercises may be focused or intentionally extended. Record the selected exercise scope and review protocol in the metadata. Use stepwise review for ordered subparts; effort is valuable when every part advances the declared target, not merely because the prompt is long.

### Fixed Open-Response Cards

Use this mode only when the visible prompt is stable, valid answers can differ materially, and each answer can be checked directly without comparison to a canonical exemplar.

Before adding one:

1. Co-design the learning target, exercise scope, exact visible prompt, review protocol, and required answer form.
2. Draft the exact Front metadata and rubric-only Back using `references/generative-blueprints.md`. Do not store a canonical answer as the grading anchor.
3. Privately produce and validate at least three distinct correct responses (non-isomorphic where applicable) and two plausible material errors. Confirm that the frozen criteria accept every correct response and reject the errors.
4. Ensure the prompt requests every element the rubric requires and the direct validation method can evaluate the learner's own response.
5. Obtain approval for the exact Front and Back, add with duplicate prevention, verify through `notesInfo`, and then update the tracker.

An optional exemplar may verify solvability or explain feedback, but label it non-exhaustive and never grade by similarity to it.

### Generated-Problem Blueprints

Before adding a blueprint:

1. Co-design the learning target, exercise scope, review protocol, and exercise family with the learner. Default to focused; use an extended worksheet when the learner values the synthesis and the topic warrants the effort.
2. Draft the exact Front blueprint and Back contract using `references/generative-blueprints.md`.
3. Generate and validate at least three candidate instances privately to test structural variety, solvability, and stable difficulty.
4. Reject a family whose variants differ only cosmetically, whose decisive cue reveals the answer, whose instructions blur givens with learner actions, or whose unrelated steps create competing difficulty. For extended worksheets, verify every part and the stepwise order independently.
5. Obtain approval for the exact blueprint and contract, create or reuse the approved subdeck and shared note type, add with duplicate prevention, verify through `notesInfo`, and then update the tracker.

Do not hardcode a subject or deck into the reusable workflow. Do not modify a grader add-on or MCP server merely to generate exercises during chat review.

## Response Pattern

For a clean add, respond briefly with:

- Added and verified status
- Note ID
- Front and back, only if useful
- Tracker updates, if a tracker is in use

For a blocked add, respond with:

- The reason it should not be added yet
- The smallest corrected version
- Which topic coverage it would support once approved

## Anki Safety

Treat `addNote`, `addNotes`, field updates, tags, deck moves, suspensions, and deletions as writes. Perform them only when the user has requested or approved that action.

Never modify Anki database files directly.
