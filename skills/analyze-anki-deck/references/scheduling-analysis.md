# Scheduling, Lapses, And FSRS Analysis

Use this reference with deck-specific Anki stats and AnkiConnect card data. It is a practical interpretation guide, not a reason to overfit tiny samples.

## Data To Inspect

From the deck-specific stats export:

- New, learning, relearning, young, mature counts.
- Reviews/day and time/card.
- Again rate.
- Young retention, mature retention, and all review retention.
- Future due burden and backlog.
- Median interval and stability.
- Median difficulty.
- Average retrievability.
- FSRS desired retention if visible.

From AnkiConnect `cardsInfo`:

- `reps`: total repetitions.
- `lapses`: number of times the card returned to relearning.
- `interval`: current interval.
- `factor`: legacy ease/factor field; less central under FSRS but still a rough signal in mixed histories.
- `type` and `queue`: card state.
- `nextReviews`: what Anki currently predicts for each answer button.
- note fields, tags, and grader instructions.

## Interpretation Rules

### Sample Size

Do not make strong claims from tiny samples.

- 0 mature cards: mature retention is unknown, not bad.
- Fewer than about 50 young reviews: young retention is noisy.
- A few bad days can reflect hard cards or a new deck, not necessarily broken scheduling.
- Newly switched FSRS decks need time to calibrate.

### Retention

Low retention can mean different things:

- Hard but valuable material.
- Overloaded or vague cards.
- Missing prerequisite cards.
- Too many new cards.
- Desired retention set too low.
- FSRS not yet calibrated to the deck.

If retention is below target and workload is low:

- Consider raising desired retention.
- Prefer fixing overloaded cards first if misses cluster on specific cards.

If retention is below target and workload is high:

- Reduce new cards.
- Split or suspend bad cards.
- Fix formulation before raising desired retention.

If retention is high and workload is comfortable:

- The deck can probably tolerate more new cards or harder application cards.

If retention is high and workload is high:

- Consider lowering desired retention only if the user accepts more forgetting.

### Lapses

Treat lapses as a triage signal.

High-lapse cards often fall into one of these types:

- Ambiguous prompt.
- Too much information in one answer.
- Similar concepts or visuals interfering.
- Missing prerequisite.
- Bad or misleading answer.
- Card asks for exact detail that the user does not actually need.

Recommended response:

1. Inspect the actual front/back.
2. Determine whether the miss is formulation, prerequisite, interference, or genuinely hard content.
3. Recommend an edit or support card.

Do not automatically delete or suspend lapsed cards. Some lapsed cards are the most valuable cards in the deck.

### Difficulty

High median difficulty means FSRS expects stability to grow slowly.

Possible causes:

- Intrinsically hard domain.
- Open-ended recall.
- Interference between similar items.
- Poorly formulated prompts.
- The user is still building basics.

Good response:

- Add basic and discrimination cards.
- Split cards.
- Add examples/non-examples.
- Use images for visual domains.

Avoid:

- Treating high difficulty alone as failure.

### Stability And Interval

Stability estimates how long recall can stay near the target retrievability. Median interval and stability give a rough sense of whether cards are becoming durable.

Signals:

- Low stability with low retention: cards are not sticking.
- Low stability with high retention: deck is young or reviews are frequent.
- Rising stability over time: good sign.
- Very short intervals on many cards: formulation or prerequisite issue may be slowing progress.

### Retrievability

Average retrievability is model-predicted current recall probability. Compare it with observed retention:

- High predicted retrievability but low actual retention can mean calibration lag, hard/open-ended grading, or poor card formulation.
- Low predicted retrievability with many due cards means a backlog or intentionally delayed reviews.

Do not overreact to one mismatch; compare over several review sessions.

## FSRS Parameter Guidance

Be cautious. The analysis should usually recommend card-design changes before parameter changes.

Reasonable recommendations:

- Raise desired retention if actual retention is persistently below target and daily workload is low/manageable.
- Lower desired retention only if workload is too high and the user accepts lower recall.
- Re-optimize FSRS parameters only after enough review history accumulates and after major card-formulation problems are addressed.
- Do not re-optimize repeatedly after every small batch or short review window.

For newly switched FSRS decks:

- Establish a baseline.
- Review consistently for 1-2 weeks.
- Watch retention, workload, and lapse clusters.
- Avoid aggressive parameter tuning immediately.

## Output Guidance

When reporting scheduling issues, tie them back to deck behavior:

```text
The low young retention is probably partly real difficulty because the sampled cards ask for open-ended visual recall. I would first add discrimination cards and simplify the worst lapsed cards before changing FSRS.
```

For lapsed card recommendations:

```text
Card: "Describe the flag of X"
Signal: high lapse count / repeated misses
Likely issue: overloaded visual recall
Edit: split into broad layout, distinguishing feature, and confusion-pair cards
```

