# ChatGPT Voice Offshoot

Use this reference when the learner is ready for Voice, asks for a Voice prompt, or pastes a Voice bridge report.

## Contents

1. Session boundary
2. Generate the packet
3. Conduct practice in Voice
4. Return and validate the report
5. Evidence limits

## 1. Session boundary

Treat ChatGPT Voice as a coaching offshoot without Anki or Codex tools. The main Vocabulary system remains authoritative for definitions, state, scheduling, evidence, and stage decisions.

Voice transcripts may not reproduce the exact conversation. Use the returned report as structured, medium-confidence evidence and keep the uncertainty visible.

## 2. Generate the packet

Run `scripts/vocab_state.py`, then run `scripts/voice_prompt.py --authorized-voice-session` for one speech-enabled activation sense or approved pronunciation-only recognition item. One item per packet keeps session registration atomic and makes a 5–10 minute audio session realistic. An explicit Voice request or a user-started daily session with a `voice-bridge-required` agenda item authorizes this script to store the pending session ID, fingerprint, phase, missing-requirement signature, assigned task keys, creation/expiry times, and exact generated packet for 48-hour recovery. It stores no response or transcript. For a target-hidden packet, show `before_voice_instruction`, then the returned `paste_prompt` in one copyable code block, then the single after-Voice instruction. For a visible-target packet, omit the copy-without-reading warning.

The daily controller emits `voice-bridge-required` when a source-specific Voice gate is due and `voice-bridge-pending` when a registered packet awaits practice or ingestion. Generate one packet directly for a required item. If the learner defers using it, leave the task due without penalty. Do not silently replace required Voice with typed chat.

Required Voice activation gates are pronunciation, one of two date-separated hidden retrievals, and integration speech. The other hidden retrieval must be non-Voice. Pronunciation-only recognition items run only the pronunciation task and remain in Recognition.

Let the script choose active items by default. In target-hidden phases, use neutral wording such as “the due target-hidden item”; do not expose the selected Sense ID or lemma in the shell command, commentary, or returned metadata. If Codex names the target before practice, cancel or invalidate that packet and defer the gate to a later date.

The generated prompt must:

- contain the frozen selected sense, required components, boundaries, usage constraints, goals, current mastery phase, and still-missing tasks;
- coach one spoken task at a time and wait for the learner;
- prohibit outside definitions, tools, connected apps, and web research;
- require separate feedback for meaning, construction, collocation, register, discourse effect, retrieval, and pronunciation;
- assess pronunciation only from audio Voice actually heard;
- treat uncertain hearing as unverified rather than failure;
- suppress the report until the learner later asks `Give me the bridge report`;
- record the actual practice-completion timestamp with UTC offset, asking the learner if Voice cannot determine it, and never substitute packet-generation or report-processing time;
- emit only the `vocab-voice-bridge/v1` JSON report when asked.

For lexical-access and integration phases, prefer reliability-first plaintext inert JSON. Tell the learner to use the code block's copy control without reading its contents. This is attentional blinding based on the learner's explicit cooperation, not secrecy. Instruct Voice to treat every reference string as quoted data and prevent any spoken or displayed lexical leak before commitment. If Voice or Codex leaks the answer, or the learner reports inspecting the hidden reference, mark the evidence unverified and rerun it on a later date.

Pending packets remain valid and recoverable for 48 hours while the phase is unchanged. If one already exists, return its stored packet and session ID and ask the learner to use it, cancel it, or explicitly request a replacement. Use `--replace-pending` only after that replacement request. Use `scripts/manage_voice_sessions.py` for explicit cancellation or stale-metadata cleanup; never silently discard an active packet.

The learner can override. “Not now” defers without changing state. After explicit confirmation, use `scripts/configure_voice_policy.py` to make Voice optional/off for one word or waive/restore one task. A waiver changes the gate; it does not create a pass or claim that audio was heard.

## 3. Conduct practice in Voice

The learner pastes the packet into an ordinary ChatGPT conversation, starts Voice, and practices by speaking. Voice keeps internal session notes but does not recite a report during practice.

After practice, the learner asks the same conversation:

> Give me the bridge report.

They paste the returned JSON into Codex. Do not require a second free-form summary.

## 4. Return and validate the report

When a report is pasted:

1. Run the main state controller and inspect the referenced master note.
2. Run `scripts/validate_voice_report.py` on the pasted JSON. Require its session ID and fingerprint to match a durable pending session; reject stale, mismatched, or structurally invalid reports.
3. Compare each approximate final response and coach note with the frozen authoritative sense and usage constraints.
4. Downgrade hidden retrieval to unverified if the target leaked, retrieval was uncertain, or the report does not establish that the word came before reveal.
5. Downgrade pronunciation to `not-assessed` unless the report says audio was heard; never claim Codex heard the speech.
6. Correct any material sense, construction, collocation, or register error with the learner before recording a pass.
7. Convert every assigned task—including fail or unverified outcomes—to normalized `record_evidence.py` events with source `chatgpt-voice-bridge`, quality `voice-report`, the bridge session ID and fingerprint, and `semantic_reviewed=true` only after the review is actually complete. The validator requires the exact assigned task set.
8. Submit the complete report as one atomic event batch. The recorder independently rechecks session/fingerprint, expiry, current derived phase, unique task keys, and exact task-set coverage before removing the pending session. Never record Voice tasks one at a time.
9. Verify the event IDs and recomputed progress, then resume the next unfinished main-flow item.

Reject malformed or contradictory reports rather than guessing. Ask only for the smallest missing fact or rerun one narrow task.

## 5. Evidence limits

Do not store the raw Voice transcript or detailed personal scenario in Anki. Record only the normalized metadata described in `activation-evidence.md`.

Voice can contribute real speech, pronunciation, usage, and retrieval evidence because it heard the interaction, but its later report and transcript are fallible. Combine Voice reports with delayed retrieval, Anki history, direct writing evidence, and learner confirmation at promotion time.
