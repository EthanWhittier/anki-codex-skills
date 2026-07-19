# AI-Grader-Aware Card Design

Use this reference when a note type supports AI grading or when designing conceptual, explanation, or reasoning cards.

## Grader Model

- The grader may receive the front, learner answer, reference back, deck instructions, card-level grader instructions, images or note context, and general knowledge.
- When a reference back exists, it is the grading anchor, but not a transcript the learner must reproduce.
- Grade meaning rather than wording overlap. Accept correct paraphrases, equivalent terminology, harmless formatting differences, and minor language errors.
- Remain strict about meaning-bearing facts. Missing material facts, contradictions, vague answers, or answers that do not address the prompt should fail.
- Do not require textbook phrasing, unnecessary precision, examples, symbols, or background facts unless the front or grader instructions request them.
- Card and deck grader instructions are trusted controls for strictness, accepted alternatives, required details, and common errors.
- Reference-free grading may use the front, trusted instructions, context, and general knowledge when the add-on enables it. It is more flexible but may have lower confidence than a precise reference-backed card.

## Design Workflow

1. Identify the learning target.
   - Ask: What should the learner understand or be able to do later?
   - Ask: What future mistake is this card preventing?
   - Ask the learner how important the topic is and how many cards it warrants before treating complexity as a reason for a richer sequence.
   - Do not create the card while the underlying concept is still unresolved.

2. Choose the card role.
   - Use reference-backed cards for definitions, formulas, logical forms, canonical examples, vocabulary, and narrow distinctions.
   - Consider reference-free grading for mechanisms, predictions, analogies, critiques, failure modes, and genuinely open-ended explanations.
   - Use either mode for examples, non-examples, counterexamples, error diagnosis, and transfer, depending on how constrained a correct answer should be.
   - Never choose reference-free grading without the user's approval and confirmation that the grader is configured to allow it.

3. Write the front.
   - State whether the learner should define, distinguish, explain, predict, diagnose, apply, or provide an example or counterexample.
   - Cue the kind and depth of answer without revealing it.
   - Separate supplied facts and constraints from learner actions. Use direct procedural wording.
   - Do not visually emphasize or quote the answer when identification is being tested.
   - Ask for comparison with an alternative only when making that contrast is itself the learning target.
   - Avoid broad prompts whose grader instructions secretly demand several unstated facts.

4. Write the back.
   - Give the smallest sufficient correct answer for the task the front asks.
   - For an intentional extended worksheet, give part-specific anchors and keep the ordered parts aligned with stepwise review.
   - Include only meaning that should influence grading.
   - Prefer a crisp conceptual anchor over a long textbook paragraph.
   - Keep teaching commentary, extra examples, and related facts out of the grading anchor unless they are required.
   - Leave the reference back empty only for an explicitly approved reference-free card.

5. Write grader instructions.
   - Name the essential meaning-bearing fact or relationship.
   - Accept equivalent prose, notation, terminology, or examples when appropriate.
   - State whether symbols, exact names, examples, or formal vocabulary are required or optional.
   - Reject specific material confusions, not merely different wording.
   - Do not make the grader demand more than the front and back establish.

6. Check deck cohesion.
   - Pair definitions with examples or recognition cards.
   - Pair rules with mechanisms, allowed applications, and failure cases.
   - Add contrast cards for confusable concepts.
   - Add transfer cards only after the foundational concept is understood.
   - Track coverage and the learner-approved card budget without treating every nearby topic as an immediate gap or completing the full card-type palette.
   - Concentrate mechanisms, error diagnosis, transfer, and extended worksheets on complicated, confusable, or high-leverage topics.

## Card-Type Palette

- **Definition:** What is X?
- **Recognition:** Which concept or rule is operating here?
- **Distinction:** How do X and Y differ?
- **Example/non-example:** Why is this an instance of X, or why is it not?
- **Mechanism:** Why does X work?
- **Application:** Apply X to this concrete case.
- **Prediction:** What changes if this assumption changes?
- **Counterexample:** Give or recognize a case that disproves the claim.
- **Error diagnosis:** What is wrong with this reasoning or move?
- **Failure mode:** What goes wrong when a restriction is violated?
- **Transfer/analogy:** How does the same structure appear in a new setting?
- **Extended worksheet:** Work through an ordered, high-value synthesis one part at a time.

## Alignment Audit

Before adding, check:

- Does the front clearly signal the expected answer type?
- Could a conceptually correct paraphrase pass?
- Does the back answer exactly what the front asks?
- Do grader instructions require any unstated facts?
- Is the reference back so narrow that it would reject valid reasoning?
- Is the card testing one retrievable unit or one explicitly chosen coherent synthesis?
- If it is multi-part, does every part serve the declared target and have its own visible prompt and grading criterion?
- Does the learner understand the concept rather than merely recognize wording?
- Does this card prevent a useful future mistake or support a coherent sequence?
