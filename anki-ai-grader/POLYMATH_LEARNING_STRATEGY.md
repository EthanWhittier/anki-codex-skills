# Polymath Learning Strategy With AI-Graded Anki

This document summarizes the learning strategy discussed for using Anki plus
AI grading to build both factual knowledge and flexible reasoning.

## Core Principle

Critical thinking is only useful when it has facts to work with. The goal is not
to replace definition cards with open-ended reasoning cards, but to use both:

- Facts give concepts crisp handles.
- Distinctions prevent category confusion.
- Mechanisms explain why things happen.
- Predictions force models to do work.
- Failure modes prevent overreach.
- Analogies connect fields while testing limits.
- Canonical examples anchor abstractions in memory.

The best pattern is:

```text
definition -> distinction -> example -> mechanism -> prediction -> failure mode -> analogy
```

Not every concept needs every card type, but this sequence is a useful checklist.

## Recommended Mix

Early in a domain:

```text
60% facts, definitions, forms, and terms
25% distinctions and boundaries
15% applications and mechanisms
```

Later in a domain:

```text
25% facts
30% distinctions
35% applications, mechanisms, and predictions
10% synthesis, analogy, and judgment
```

The danger is not factual cards. The danger is orphan facts: facts that never get
used in a later card.

## Card Types

### Definition Cards

Use when a term needs a crisp handle.

```text
Define validity in deductive logic.
```

Expected answer:

```text
An argument is valid when its conclusion must be true if its premises are true.
```

### Distinction Cards

Use when two nearby ideas are often confused.

```text
Distinguish validity from soundness.
```

Expected answer:

```text
Validity means the conclusion follows from the premises. Soundness means the
argument is valid and all premises are true.
```

### Canonical Example Cards

Use to attach an abstract idea to a memorable case.

```text
Give a valid argument with a false premise.
```

Expected answer:

```text
All cats are reptiles. Felix is a cat. Therefore, Felix is a reptile.
```

### Mechanism Cards

Use when the important question is why something follows.

```text
Why is modus tollens valid?
```

Expected answer:

```text
If P guarantees Q, then Q being false means P could not have been true.
```

### Prediction Cards

Use when a model should imply an outcome.

```text
If supply decreases while demand is unchanged, what happens to equilibrium price
and quantity?
```

Expected answer:

```text
Price rises and quantity falls.
```

### Failure Mode Cards

Use to remember how a concept is commonly misused.

```text
What is a common mistake about valid arguments?
```

Expected answer:

```text
Thinking that a valid argument must have true premises or a true conclusion.
```

### Analogy Cards

Use to connect domains, but always include the limit of the analogy.

```text
How is evolution by natural selection analogous to market competition, and where
does the analogy break?
```

Expected answer:

```text
Both involve variation, selection, and differential survival. The analogy breaks
because markets involve intentional agents, institutions, and foresight.
```

## Logic Example: Conditional Reasoning

A small cluster for learning conditionals might look like this:

```text
Define a conditional.
When is P -> Q false?
What is modus ponens?
Why is modus ponens valid?
What is modus tollens?
Why is modus tollens valid?
What is affirming the consequent?
Why is affirming the consequent invalid?
What is denying the antecedent?
Give a counterexample to denying the antecedent.
Distinguish sufficient from necessary conditions.
In P -> Q, which side is sufficient and which side is necessary?
```

This cluster mixes exact recall, distinctions, mechanisms, and counterexample
practice.

## Grader Notes

Use grader notes to control strictness.

For exact form cards:

```text
Require the exact logical form using P and Q.
```

For explanation cards:

```text
Accept any explanation that identifies the impossible case: P true and Q false.
```

For counterexample cards:

```text
The answer must provide a case where the premises are true and the conclusion is
false.
```

## When To Use Reference Answers

Use reference answers for precision:

- definitions
- formulas
- logical forms
- canonical examples
- exact distinctions
- vocabulary

Use reference-free AI grading for generative reasoning:

- mechanisms
- predictions
- analogies
- critiques
- failure modes
- open-ended explanations

The strongest system uses both: reference answers for crisp anchors, and
reference-free grading for flexible thinking.

## The Card-Making Question

When making a card, ask:

```text
What future mistake is this card preventing?
```

Examples:

- A definition card prevents word fog.
- A distinction card prevents category confusion.
- A mechanism card prevents magical thinking.
- A prediction card prevents inert knowledge.
- A failure-mode card prevents overreach.
- A canonical example card prevents abstraction drift.
- An analogy card prevents siloed knowledge.

