# AI Grader Application Behavior

This document summarizes how the Anki AI grader add-on behaves after the changes
discussed in this session.

## Review Flow

1. The learner enters an answer.
2. The add-on waits until the answer side is shown.
3. The add-on gathers card context:
   - flashcard prompt
   - learner answer
   - reference answer, if available
   - deck-level grader instructions
   - card or note-level grader notes
   - optional note fields
4. The add-on sends the grading request to the OpenAI Responses API.
5. The model returns structured JSON:
   - `recommendedOutcome`: `again` or `good`
   - `confidence`: decimal from `0` to `1`
   - `auditSummary`: empty for `good`, concise reason for `again`
6. The add-on displays the recommendation in Anki.
7. If `auto_apply_grade` is enabled, the add-on answers the card automatically
   after the configured delay.
8. If local logging is enabled, the add-on writes token usage to the profile log.

## Reference Answer Behavior

If a reference answer is present, it is sent to the model and treated as the
grading anchor.

This is best for cards where precision matters:

- definitions
- formulas
- exact logical forms
- canonical examples
- vocabulary
- narrow distinctions

The system prompt tells the model to judge meaning rather than wording overlap,
but to treat the reference answer as the anchor when one exists.

## Reference-Free Behavior

The config flag is:

```json
"allow_grading_without_reference": true
```

When this flag is enabled and no reference answer is found, the add-on still
grades the card. The request explicitly tells the model:

```text
No reference answer was provided. Grade using the flashcard prompt, trusted
grader instructions, available note fields, learner answer, and general
knowledge.
```

This is useful for cards where a single stored answer would be too narrow:

- mechanisms
- predictions
- analogies
- critiques
- failure modes
- open-ended explanations

If the flag is disabled and no reference answer is found, the add-on refuses to
grade and shows a message.

If the flag is enabled but a reference answer exists, normal reference-answer
grading still happens. The flag only changes the no-reference case.

## Grader Instructions

Deck-level grader instructions and card-level grader notes are trusted grading
instructions. They can control strictness, accepted variants, required details,
and feedback style.

Examples:

```text
Require the exact logical form using P and Q.
```

```text
Accept any explanation that identifies why Q could be true for reasons other
than P.
```

```text
The answer must include a true-premise, false-conclusion counterexample.
```

These notes are especially important for reference-free cards because they
define what counts as a good answer.

## Prompt Cache Behavior

The add-on sends a stable system prompt before the changing card content. This
allows repeated grading calls to use OpenAI prompt caching once the stable prefix
is long enough.

The observed behavior after adding a small static prompt nudge was:

```text
First warmed request: cachedInputTokens=0
Later requests:        cachedInputTokens=1024
```

That means the stable prefix reached the minimum cacheable range and later
requests reused the cached prefix. The changing card-specific tail remains
uncached, which is the desired shape.

The prompt version is included in the cache key:

```text
flashcards-grading-{PROMPT_VERSION}
```

When the prompt version changes, the cache needs to warm again.

## Local Usage Log

The add-on writes successful grading usage to:

```text
<Anki profile folder>/ai_grader.log
```

On the tested machine, that path was:

```text
~/Library/Application Support/Anki2/User 1/ai_grader.log
```

The default log config is:

```json
"enable_local_log": true,
"local_log_max_bytes": 262144,
"local_log_backup_count": 0
```

This keeps a single bounded log file capped at 256 KB. No backup log files are
kept.

Each log line includes:

- model
- card id
- input tokens
- output tokens
- total tokens
- cached input tokens
- reasoning tokens
- outcome
- confidence
- response id

Example shape:

```text
[grading] token usage model=gpt-5.4-2026-03-05 cardId=... inputTokens=...
outputTokens=... totalTokens=... cachedInputTokens=1024 reasoningTokens=...
outcome=good confidence=...
```

## Cost Estimation Flow

To estimate cost:

1. Compute average input tokens.
2. Compute average cached input tokens.
3. Compute average uncached input tokens:

```text
uncachedInputTokens = inputTokens - cachedInputTokens
```

4. Compute average output tokens.
5. Apply current model pricing:

```text
monthlyCost =
  requestsPerMonth *
  (
    uncachedInputTokens * inputPricePerToken +
    cachedInputTokens * cachedInputPricePerToken +
    outputTokens * outputPricePerToken
  )
```

The observed steady-state pattern was roughly:

```text
Average input tokens:        about 1294
Average cached input tokens: 1024
Average uncached input:      about 270
Average output tokens:       about 71
```

That means most input tokens were cached after warm-up, giving a large
steady-state savings compared with uncached input.

## Current Config Additions

The relevant config values added during this session are:

```json
"enable_local_log": true,
"local_log_max_bytes": 262144,
"local_log_backup_count": 0,
"allow_grading_without_reference": true
```

## Practical Operating Model

Use the add-on in two modes:

```text
Reference-answer mode:
Use for crisp factual recall and exactness.

Reference-free mode:
Use for reasoning, explanation, critique, analogy, and prediction.
```

The goal is a system that supports both memory and judgment:

```text
facts for handles
AI grading for flexible use
Anki scheduling for long-term retention
local logs for cost and cache visibility
```
