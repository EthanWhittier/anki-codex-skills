from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from vocab_runtime import derive_progress, initial_ledger, initial_state, phase_audit


SENSE_ID = "example.n.sense"


def event(
    task: str,
    occurred: str,
    *,
    source: str = "codex-chat",
    quality: str = "direct-chat",
    modality: str = "writing",
    count: int = 1,
    contexts: list[str] | None = None,
    audio_heard: bool = False,
    pronunciation: str = "not-assessed",
    novel: bool = True,
) -> dict:
    return {
        "id": f"evt-{task}-{occurred}-{source}",
        "occurred_at": f"{occurred}T12:00:00-06:00",
        "source": source,
        "evidence_quality": quality,
        "phase": {
            "meaning-boundary": "anchor",
            "pronunciation": "anchor",
            "visible-use": "anchor",
            "neighbor-distinction": "distinguish",
            "grammar-collocation": "distinguish",
            "misuse-diagnosis": "distinguish",
            "controlled-use": "controlled-production",
            "hidden-retrieval": "lexical-access",
            "integration-speech": "integration",
            "integration-writing": "integration",
            "delayed-definition": "integration",
        }[task],
        "task": task,
        "modality": modality,
        "target_visibility": "hidden" if task in {"hidden-retrieval", "integration-speech"} else "visible",
        "result": "pass",
        "count": count,
        "context_keys": contexts or [task],
        "novel_context": novel,
        "target_retrieved_before_reveal": task in {"hidden-retrieval", "integration-speech"},
        "target_revealed_early": False,
        "audio_heard": audio_heard,
        "pronunciation": pronunciation,
        "errors": [],
    }


def voice_event(task: str, occurred: str, **kwargs) -> dict:
    return event(
        task,
        occurred,
        source="chatgpt-voice-bridge",
        quality="voice-report",
        modality="speech",
        audio_heard=True,
        **kwargs,
    )


def through_controlled() -> list[dict]:
    return [
        event("meaning-boundary", "2026-07-19"),
        voice_event("pronunciation", "2026-07-19", pronunciation="pass"),
        event("visible-use", "2026-07-19", count=2, contexts=["a", "b"]),
        event("neighbor-distinction", "2026-07-21"),
        event("grammar-collocation", "2026-07-21"),
        event("misuse-diagnosis", "2026-07-21"),
        event("controlled-use", "2026-07-24", count=3, contexts=["c", "d", "e"]),
    ]


class VoicePolicyTests(unittest.TestCase):
    def activation_state(self, policy: str | None = None) -> dict:
        state = initial_state(
            SENSE_ID,
            date(2026, 7, 19),
            goals=["speech", "writing"],
            recording_authorized=True,
            voice_enabled=True,
        )
        if policy is None:
            state.pop("voice_policy", None)
        else:
            state["voice_policy"] = policy
        return state

    def test_legacy_voice_enabled_speech_defaults_to_required(self) -> None:
        audit = phase_audit([], ["speech"], self.activation_state())
        self.assertIn("voice-pronunciation", audit["anchor"]["missing"])

    def test_direct_hidden_retrieval_today_enters_spacing_hold(self) -> None:
        state = self.activation_state()
        ledger = initial_ledger(SENSE_ID)
        ledger["events"] = through_controlled() + [event("hidden-retrieval", "2026-08-06")]
        progress = derive_progress(state, ledger, date(2026, 8, 6))
        self.assertEqual("spacing-hold", progress["current_phase"])
        self.assertEqual("2026-08-07", progress["unlocks_on"])
        self.assertFalse(progress["voice_due"])
        self.assertIn("voice-hidden-retrieval", progress["missing"])

    def test_lexical_access_requires_mixed_modalities_on_different_dates(self) -> None:
        events = through_controlled() + [
            event("hidden-retrieval", "2026-08-06"),
            voice_event("hidden-retrieval", "2026-08-07"),
        ]
        audit = phase_audit(events, ["speech", "writing"], self.activation_state())
        self.assertTrue(audit["lexical-access"]["complete"])

    def test_required_voice_rejects_written_integration_substitution(self) -> None:
        events = through_controlled() + [
            event("hidden-retrieval", "2026-08-01"),
            voice_event("hidden-retrieval", "2026-08-03"),
            event("integration-writing", "2026-08-05"),
            event("delayed-definition", "2026-08-05"),
        ]
        audit = phase_audit(events, ["speech", "writing"], self.activation_state())
        self.assertIn("voice-integration-speech", audit["integration"]["missing"])

    def test_optional_policy_restores_flexible_integration(self) -> None:
        state = self.activation_state("optional")
        events = through_controlled() + [
            event("hidden-retrieval", "2026-08-01"),
            event("hidden-retrieval", "2026-08-03"),
            event("integration-writing", "2026-08-05"),
            event("delayed-definition", "2026-08-05"),
        ]
        audit = phase_audit(events, ["speech", "writing"], state)
        self.assertTrue(audit["integration"]["complete"])

    def test_pronunciation_only_profile_completes_after_heard_voice_pass(self) -> None:
        state = initial_state(
            SENSE_ID,
            date(2026, 8, 6),
            goals=["speech"],
            recording_authorized=True,
            voice_enabled=True,
        )
        state["status"] = "pronunciation-only"
        ledger = initial_ledger(SENSE_ID)
        pending = derive_progress(state, ledger, date(2026, 8, 6))
        self.assertTrue(pending["voice_due"])
        ledger["events"] = [voice_event("pronunciation", "2026-08-06", pronunciation="pass")]
        complete = derive_progress(state, ledger, date(2026, 8, 6))
        self.assertEqual("pronunciation-complete", complete["current_phase"])

    def test_explicit_pronunciation_waiver_does_not_create_evidence(self) -> None:
        state = self.activation_state()
        state["voice_waivers"] = ["pronunciation"]
        audit = phase_audit([], ["speech"], state)
        self.assertNotIn("pronunciation", audit["anchor"]["missing"])
        self.assertNotIn("voice-pronunciation", audit["anchor"]["missing"])


if __name__ == "__main__":
    unittest.main()
