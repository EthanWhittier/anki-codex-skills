# Practice Exercise Schemas

Use this reference to design either a fixed open-response exercise or an exercise family whose problem Codex generates during chat review.

## Selection

Prefer a fixed card for stable facts, notation, rules, canonical examples, and narrow conceptual distinctions.

Prefer a fixed open-response card when one stable prompt admits many materially different valid constructions, explanations, arguments, models, or examples that can be checked directly.

Prefer a generated-problem blueprint when success requires repeated application to unseen cases, such as translation, diagnosis, counterexamples, proof steps, calculation, program tracing, or transfer.

One blueprint must test one identifiable capability within a reasonably stable difficulty band. Split broad synthesis families until a failure can be attributed to a specific capability.

## Shared Structure

- Note type: `Codex Generative Exercise`
- Schema marker: `codex-open-response-exercise/v1` or `codex-generative-exercise/v1`
- Suggested subdeck: `<Subject or Topic Deck>::Generative Practice`
- Fields: `Front`, `Back`, `AI Grader Instructions`
- Tags: `codex-open-response` or `codex-generative` plus subject- and topic-specific tags

The Front is hidden metadata containing either an exact visible prompt or a generation blueprint. The Back is a hidden grading contract. Leave `AI Grader Instructions` blank unless the learner requests another use; chat review consumes the Front and Back.

## Fixed Open-Response Schema

Use this mode only when the prompt remains fixed and the learner may supply any directly verifiable valid answer. The Back defines invariant criteria, not a canonical response.

### Front metadata

```text
Schema: codex-open-response-exercise/v1
Subject context:
Learning target:
Visible prompt:
Prerequisites:
Source or knowledge boundary:
Difficulty:
Answer freedom:
Allowed tools or references:
Direct validation method:
```

### Back contract

```text
Correctness conditions:
Required reasoning:
Accepted alternatives:
Material errors:
Direct validation method:
Optional exemplar policy:
```

The visible prompt must request everything in `Correctness conditions` and `Required reasoning`. `Accepted alternatives` must make genuine answer freedom explicit. `Direct validation method` must evaluate the learner's submitted object, argument, or construction itself rather than compare it with an exemplar.

Do not require an enumerated domain, explicit extension, canonical notation, or another particular representation unless producing that representation is itself the learning target. If an ordinary-language description supplies enough information for direct validation, accept it when the contract allows it.

Before finalizing, privately validate at least three distinct correct responses (non-isomorphic where applicable) and two plausible incorrect responses. Reject or narrow the card if the same frozen criteria cannot distinguish them reliably. An exemplar is optional, non-exhaustive, and never the grading anchor.

## Generated-Problem Schema

### Front blueprint

```text
Schema: codex-generative-exercise/v1
Subject context:
Learning target:
Task family:
Prerequisites:
Source or knowledge boundary:
Variation dimensions:
Difficulty:
Generation constraints:
Required answer form:
Allowed tools or references:
Verification method:
```

### Back contract

```text
Correctness conditions:
Required reasoning:
Accepted equivalents:
Material errors:
Reference solution method:
```

## Shared Co-Design Flow

1. Propose the learning purpose and one narrow exercise family.
2. Let the learner critique the target, constraints, answer freedom, and desired difficulty.
3. Draft the exact blueprint and contract together.
4. Keep all subject-specific rules and authoritative sources in the blueprint or contract.
5. Require approval before any deck, note-type, or note write.

## Generated-Problem Preflight Quality Gate

Privately generate at least three candidate instances before finalizing the blueprint. Independently solve and verify each one. Do not show hidden solutions unless requested.

Require all of the following:

- Variants change meaningful structure along declared dimensions, not merely names, numbers, labels, or predicates.
- Difficulty remains within the declared band.
- Every problem is self-contained and unambiguous.
- The visible prompt requests everything the rubric requires.
- No undeclared prerequisite or convention is needed.
- The verification method can actually establish correctness.
- Non-target steps are transparent and verified so they do not become a competing source of failure.
- Decisive facts are available but do not simply announce the answer unless explicit calibration is the target.
- Accepted equivalents cover legitimate alternate representations or reasoning.
- Material errors identify meaning-changing failures rather than wording differences.

Reject or narrow the blueprint when three sound, structurally distinct instances cannot be produced at comparable difficulty.

## Domain-Neutral Boundaries

Use source excerpts or authoritative references when correctness depends on supplied material. Avoid changing current facts unless the blueprint supplies a dated source snapshot. For high-stakes subjects, require an authoritative source boundary and explicit verification.

Choose verification appropriate to the domain: symbolic derivation, independent calculation, code execution, test cases, source comparison, or another explicit method. Never claim verification that was not performed.

Do not encode subject-specific generation rules in the reusable skill. A future non-logic blueprint must work without changing this workflow.

## Creation and Verification

Inspect deck and model names for conflicts. Reuse the shared note type when present. Create the subject's generative subdeck only with approval. Add with deck-scoped duplicate prevention, verify the returned note ID and fields with `notesInfo`, and record the note ID and learning target in the subject tracker.
