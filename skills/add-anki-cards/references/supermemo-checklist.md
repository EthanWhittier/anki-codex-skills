# SuperMemo-Style Card Formulation Checklist

Use this checklist to judge proposed Anki cards before adding them.

Source inspiration: https://www.supermemo.com/en/blog/twenty-rules-of-formulating-knowledge

## Gate

- Retain material with its basic meaning and relevant conditions understood. Deeper explanation and transfer can develop later; do not withhold useful foundational cards until advanced mastery. If the card depends on an unclear prerequisite, help resolve it first.
- Use minimum information as the default for ordinary retrieval cards, not as a prohibition on deliberate synthesis.
- Choose an explicit scope: atomic retrieval, focused exercise, or extended worksheet.
- Keep ordinary retrieval cards to one small thing: a fact, contrast, rule, translation pattern, or example.
- Allow an extended worksheet when its ordered parts form one coherent learning arc, the topic is high priority or complicated, and the additional effort is intended to produce useful reasoning practice.
- Split multi-part work when the parts are independent, incidental, or impossible to grade step by step. Do not split merely because a valuable proof or synthesis takes effort.
- Let the learner determine topic priority and acceptable deck load. Use complexity and confusability to allocate an approved budget, not to enlarge it automatically.
- Budget coverage explicitly using `learning-map.md` for multi-topic work. Separate total coverage from the next authoring batch; do not mechanically add every card type or assume a tiny first batch covers a section.
- Avoid sets and enumerations unless the list is small, stable, and genuinely the item to learn.
- Avoid vague prompts that could have many correct answers.
- Avoid cards that require reconstructing a long paragraph.
- Prefer concrete examples when a rule is easy to confuse.
- Prefer contrast cards for confusable ideas.

## Add Directly When

- The card is correct.
- The prompt has a clear target.
- The answer is short enough to grade, or the exercise is intentionally extended with an explicit stepwise protocol and part-specific criteria.
- Any grammar cleanup does not change the user's wording or meaning.

## Pause Before Adding When

- The answer is wrong or overgeneralized.
- The prompt omits a key restriction.
- The card asks for multiple independent things without a synthesis rationale or stepwise grading plan.
- The answer depends on a hidden convention.
- A prerequisite concept is missing and likely to make the card rote.

## Grader Instruction Pattern

Good AI grader instructions say:

- what concept must be present;
- what equivalent phrasing is acceptable;
- what common confusion should be rejected;
- whether examples/symbols are required or optional.

Avoid putting extra teaching notes in the grader field.
