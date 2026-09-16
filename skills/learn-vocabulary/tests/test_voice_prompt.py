from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from vocab_runtime import initial_state
from voice_prompt import prompt_item


class VoicePromptTests(unittest.TestCase):
    def note(self) -> dict:
        state = initial_state(
            "example.n.false-show",
            date(2026, 7, 19),
            goals=["speech", "writing"],
            recording_authorized=True,
            voice_enabled=True,
        )
        return {
            "noteId": 123,
            "fields": {
                "Lemma": "example-target",
                "Sense ID": "example.n.false-show",
                "Pronunciation": "example pronunciation",
                "Authoritative Definition": "example definition",
                "Required Components": "one; two",
                "Working Gloss": "example gloss",
                "Grounding and Boundaries": "example boundary",
                "Usage": "example usage",
                "Activation State": json.dumps(state),
            },
            "tags": ["vocab::stage::activation", "vocab::cohort::2026-07-19"],
        }

    def test_hidden_packet_uses_plaintext_without_decode_step(self) -> None:
        progress = {
            "current_phase": "lexical-access",
            "missing": ["voice-hidden-retrieval"],
            "tasks": ["hidden-retrieval"],
        }
        block, metadata = prompt_item(self.note(), progress, 1)
        self.assertIn("BEGIN_INERT_HIDDEN_REFERENCE_JSON", block)
        self.assertIn('"target":"example-target"', block)
        self.assertIn("copy this packet without inspecting", block)
        self.assertNotIn("Base64", block)
        self.assertNotIn("Decode", block)
        self.assertIsNone(metadata["target"])
        self.assertIsNone(metadata["sense_id"])

    def test_visible_packet_keeps_normal_inert_json(self) -> None:
        progress = {
            "current_phase": "anchor",
            "missing": ["voice-pronunciation"],
            "tasks": ["pronunciation"],
        }
        block, metadata = prompt_item(self.note(), progress, 1)
        self.assertIn("BEGIN_INERT_REFERENCE_JSON", block)
        self.assertNotIn("copy this packet without inspecting", block)
        self.assertEqual("example-target", metadata["target"])


if __name__ == "__main__":
    unittest.main()
