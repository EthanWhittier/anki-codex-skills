#!/usr/bin/env python3
"""Headless contract tests for the chat-review AnkiConnect actions."""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from anki.collection import Collection
from plugin import AnkiConnect


def expect_code(code: str, callback) -> None:
    try:
        callback()
    except Exception as error:
        if not str(error).startswith(code + ":"):
            raise AssertionError(f"expected {code}, got {error}") from error
    else:
        raise AssertionError(f"expected {code}")


def add_note(col: Collection, deck_id: int, front: str) -> int:
    note = col.new_note(col.models.by_name("Basic"))
    note["Front"] = front
    note["Back"] = "disposable answer"
    col.add_note(note, deck_id)
    return int(col.find_cards(f"nid:{note.id}")[0])


def review_count(col: Collection, card_id: int) -> int:
    return int(col.db.scalar("select count(*) from revlog where cid = ?", card_id) or 0)


def make_connect(col: Collection, profile_name: str = "Disposable Chat Review") -> AnkiConnect:
    connect = AnkiConnect()
    connect.collection = lambda: col
    connect.scheduler = lambda: col.sched
    connect.window = lambda: SimpleNamespace(pm=SimpleNamespace(name=profile_name))
    connect.deckNameFromId = lambda deck_id: col.decks.name(deck_id)
    return connect


def run() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="anki-chat-review-protocol-") as tmp:
        path = Path(tmp) / "collection.anki2"
        col = Collection(str(path))
        try:
            deck_name = "Chat Review Protocol Test"
            deck_id = int(col.decks.id(deck_name))
            col.decks.select(deck_id)
            first_id = add_note(col, deck_id, "first disposable question")
            second_id = add_note(col, deck_id, "second disposable question")
            connect = make_connect(col)

            capabilities = connect.chatReviewCapabilities()
            assert capabilities["protocol"] == "chat-review/v1"
            assert capabilities["ticketProtocolVersion"] == "chat-review/v1"
            assert capabilities["ankiVersion"] in capabilities["testedAnkiVersions"]
            assert capabilities["ankiVersionVerified"] is True
            assert capabilities["fsrs"] == {"enabled": False, "scheduler": "sm2"}
            assert len(capabilities["generationHash"]) == 64
            assert "Disposable Chat Review" not in json.dumps(capabilities)

            first = connect.chatReviewNext("session-one", deck_name, True, True)
            repeated = connect.chatReviewNext("session-one", deck_name, True, True)
            assert repeated == first
            assert first["ticket"]
            assert first["card"]["cardId"] in {first_id, second_id}
            expect_code(
                "REVIEW_SESSION_BUSY",
                lambda: connect.chatReviewNext("session-two", deck_name, True, True),
            )
            expect_code(
                "REVIEW_CARD_MISMATCH",
                lambda: connect.chatReviewAnswer(
                    "session-one", first["ticket"], first["card"]["cardId"] + 1, 3
                ),
            )

            rated_id = first["card"]["cardId"]
            before = review_count(col, rated_id)
            answered = connect.chatReviewAnswer(
                "session-one", first["ticket"], rated_id, 3, True
            )
            after = review_count(col, rated_id)
            assert after - before == 1
            assert answered["replayed"] is False

            replayed = connect.chatReviewAnswer(
                "session-one", first["ticket"], rated_id, 3, True
            )
            assert replayed["replayed"] is True
            assert review_count(col, rated_id) == after
            expect_code(
                "REVIEW_TICKET_ALREADY_USED_DIFFERENT_RATING",
                lambda: connect.chatReviewAnswer(
                    "session-one", first["ticket"], rated_id, 4, True
                ),
            )

            next_ticket = answered["next"]["ticket"]
            next_card_id = answered["next"]["card"]["cardId"]
            next_before = review_count(col, next_card_id)
            cancelled = connect.chatReviewCancel("session-one", next_ticket)
            assert cancelled == {"success": True, "cancelled": True}
            assert review_count(col, next_card_id) == next_before

            abandonable = connect.chatReviewNext("abandonable", deck_name, True, True)
            abandon_card_id = abandonable["card"]["cardId"]
            abandon_card = col.get_card(abandon_card_id)
            scheduling_before = (
                abandon_card.queue,
                abandon_card.type,
                abandon_card.due,
                abandon_card.ivl,
                abandon_card.factor,
            )
            reviews_before_abandon = review_count(col, abandon_card_id)
            status = connect.chatReviewStatus()
            assert status["active"] is True
            assert status["cardId"] == abandon_card_id
            assert "ticket" not in json.dumps(status).lower()
            assert "session" not in json.dumps(status).lower()
            expect_code(
                "REVIEW_CARD_MISMATCH",
                lambda: connect.chatReviewAbandon(
                    status["generationHash"], status["ownerHash"], abandon_card_id + 1, True
                ),
            )
            abandoned = connect.chatReviewAbandon(
                status["generationHash"], status["ownerHash"], abandon_card_id, True
            )
            assert abandoned == {
                "success": True,
                "abandoned": True,
                "cardId": abandon_card_id,
            }
            abandon_card = col.get_card(abandon_card_id)
            assert review_count(col, abandon_card_id) == reviews_before_abandon
            assert (
                abandon_card.queue,
                abandon_card.type,
                abandon_card.due,
                abandon_card.ivl,
                abandon_card.factor,
            ) == scheduling_before
            assert connect.chatReviewStatus()["active"] is False

            expiring = connect.chatReviewNext("expiring", deck_name, True, True)
            connect.chatReviewPending["expiring"]["createdAt"] = (
                time.time() - connect.CHAT_REVIEW_PENDING_TTL_SECONDS - 1
            )
            expect_code(
                "REVIEW_TICKET_EXPIRED",
                lambda: connect.chatReviewAnswer(
                    "expiring", expiring["ticket"], expiring["card"]["cardId"], 3
                ),
            )
            expect_code(
                "REVIEW_TICKET_EXPIRED",
                lambda: connect.chatReviewNext("expiring", deck_name, True, True),
            )

            secret = "full-ticket-secret"
            redacted = connect.redactChatReviewLogData(
                {"params": {"ticket": secret, "sessionId": "full-session-secret"}}
            )
            assert secret not in json.dumps(redacted)
            assert "full-session-secret" not in json.dumps(redacted)

            tested_versions = connect.CHAT_REVIEW_TESTED_ANKI_VERSIONS
            connect.CHAT_REVIEW_TESTED_ANKI_VERSIONS = ()
            try:
                assert connect.chatReviewCapabilities()["ankiVersionVerified"] is False
                expect_code(
                    "ANKI_VERSION_UNVERIFIED",
                    lambda: connect.chatReviewNext("unverified", deck_name, True, True),
                )
            finally:
                connect.CHAT_REVIEW_TESTED_ANKI_VERSIONS = tested_versions

            return {
                "success": True,
                "collectionWasDisposable": True,
                "tests": [
                    "capabilities",
                    "repeat-next",
                    "single-active-session",
                    "card-mismatch",
                    "exactly-once-replay",
                    "different-rating-conflict",
                    "cancel-without-scheduling",
                    "status-without-bearer-secrets",
                    "abandon-requires-recent-exact-match",
                    "abandon-without-scheduling",
                    "expiry",
                    "expired-session-cannot-draw-fresh-card",
                    "log-redaction",
                    "unverified-version-fails-closed",
                ],
            }
        finally:
            col.close()


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
