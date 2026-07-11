# Formulation Rules For Anki Deck Analysis

Use these rules as a practical analysis lens. They summarize the SuperMemo article "Effective learning: Twenty rules of formulating knowledge" by Piotr Wozniak:

https://www.supermemo.com/en/blog/twenty-rules-of-formulating-knowledge

## Highest-Value Rules

1. Do not memorize what is not understood.
2. Learn the overall structure before memorizing details.
3. Build on basics; missing basics cause expensive downstream failures.
4. Use the minimum information principle: one card should test one small thing.
5. Use cloze deletions where they simplify conversion from text to recall.
6. Use imagery for visual knowledge.
7. Use mnemonics sparingly for stubborn material.
8. Use graphic deletion or image occlusion for visual components.
9. Avoid sets and enumerations unless split into smaller items.
10. Avoid wording that makes the answer ambiguous.
11. Use examples, non-examples, and counterexamples.
12. Reduce interference by making confusing distinctions explicit.

## Diagnosis Patterns

### Overloaded Card

Symptoms:
- Long answer.
- User must recall many independent details.
- Card gets repeated often or repeatedly missed.

Recommendation:
- Split into definition, example, mechanism, distinction, and application cards.

### Vague Prompt

Symptoms:
- Many possible valid answers.
- AI grader needs to infer too much.
- User is unsure what level of detail is expected.

Recommendation:
- Make the task explicit: define, distinguish, predict, explain why, give example, or identify key feature.
- Add grader instructions for AI-graded notes.

### Interference

Symptoms:
- User confuses nearby concepts or similar flags/maps/terms.
- Answers are almost right but swapped or reversed.

Recommendation:
- Add "Distinguish X from Y" cards.
- Add "What is easy to confuse about X?" cards.
- Add cue-to-answer and answer-to-cue directions when helpful.

### Missing Basics Within Existing Scope

Symptoms:
- Advanced cards rely on an unstated term already used in the deck.
- User misses a reasoning card because a prerequisite in the same deck is weak.

Recommendation:
- Add a basic definition or canonical example card for that prerequisite.
- Do not recommend unrelated topics merely because they belong to the subject.

### Visual Domain Problem

Symptoms:
- Cards require visual recall from text only.
- User confuses colors, shapes, order, or position.

Recommendation:
- Use images.
- Add image-to-name recognition cards.
- Add name-to-key-feature cards.
- Add distinguishing-feature cards for confusion sets.
- Avoid requiring exact minor details unless explicitly tested.

## Output Template

Use concise, evidence-based sections:

```text
Deck Health
What Is Going Well
Main Risks
Recommended Edits To Existing Cards
Recommended New Cards
Scheduling / FSRS Notes
Next Safe Actions
```

For existing-card edits, quote the current front briefly and provide a replacement or split:

```text
Current: "Describe the flag of X."
Issue: overloaded visual recall.
Better:
- "What are the main colors/layout of X's flag?"
- "What feature distinguishes X from Y?"
```

