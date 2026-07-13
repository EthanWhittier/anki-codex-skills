#!/usr/bin/env python3
"""Go/no-go proof for answering a queued card with its frozen states.

This test creates and destroys a standalone Anki collection. It never opens a
user profile or collection. Run it with the Python interpreter bundled with
the exact Anki version under test.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

import anki.buildinfo
from anki.collection import Collection
from anki.cards import Card
from anki.scheduler.v3 import CardAnswer


def queued_card(col: Collection):
    queued = col.sched.get_queued_cards(fetch_limit=1)
    if not queued.cards:
        raise AssertionError("scheduler returned no card")
    return queued.cards[0]


def materialize_card(col: Collection, queued) -> Card:
    card = Card(col, backend_card=queued.card)
    card.start_timer()
    return card


def add_basic_note(col: Collection, deck_id: int, front: str) -> int:
    notetype = col.models.by_name("Basic")
    if notetype is None:
        raise AssertionError("stock Basic note type is unavailable")
    note = col.new_note(notetype)
    note["Front"] = front
    note["Back"] = "scheduler proof"
    col.add_note(note, deck_id)
    cards = col.find_cards(f"nid:{note.id}")
    if len(cards) != 1:
        raise AssertionError(f"expected one card for note {note.id}, got {cards}")
    return int(cards[0])


def run_spike(step_minutes: float) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="anki-chat-review-spike-") as tmp:
        collection_path = Path(tmp) / "collection.anki2"
        col = Collection(str(collection_path))
        try:
            deck_id = int(col.decks.id("Chat Review Scheduler Spike"))
            col.decks.select(deck_id)

            config = col.decks.add_config(
                "Chat Review Scheduler Spike", col.decks.config_dict_for_deck_id(deck_id)
            )
            config["new"]["delays"] = [step_minutes]
            config["new"]["perDay"] = 100
            config["rev"]["perDay"] = 100
            col.decks.update_config(config)
            deck = col.decks.get(deck_id, default=False)
            assert deck is not None
            col.decks.set_config_id_for_deck_dict(deck, config["id"])

            preferences = col.get_preferences()
            preferences.scheduling.learn_ahead_secs = 0
            col.set_preferences(preferences)

            created = {
                add_basic_note(col, deck_id, "disposable card one"),
                add_basic_note(col, deck_id, "disposable card two"),
            }

            # Turn the first scheduler-selected card into learning card B.
            queued_b = queued_card(col)
            card_b = materialize_card(col, queued_b)
            sched = col.sched
            sched.answer_card(
                sched.build_answer(
                    card=card_b,
                    states=queued_b.states,
                    rating=CardAnswer.AGAIN,
                )
            )

            # With learn-ahead disabled, the other new card is presented as A.
            queued_a = queued_card(col)
            card_a = materialize_card(col, queued_a)
            if card_a.id == card_b.id:
                raise AssertionError("learning card B was returned before its due time")
            if {card_a.id, card_b.id} != created:
                raise AssertionError("scheduler returned an unexpected card")

            frozen_states = type(queued_a.states)()
            frozen_states.CopyFrom(queued_a.states)
            card_b.load()
            if card_b.queue != 1:
                raise AssertionError(f"card B is not intraday learning (queue={card_b.queue})")
            learning_due_at = int(card_b.due)
            before = int(
                col.db.scalar("select count(*) from revlog where cid = ?", card_a.id) or 0
            )

            deadline = time.monotonic() + max(10.0, step_minutes * 60 + 5.0)
            while time.monotonic() < deadline:
                if int(time.time()) >= learning_due_at:
                    break
                time.sleep(0.05)
            else:
                raise AssertionError("learning card B did not become due before timeout")

            # Critical invariant: answer A with the states frozen when A was presented,
            # even though B has since become the scheduler's top card.
            sched.answer_card(
                sched.build_answer(
                    card=card_a,
                    states=frozen_states,
                    rating=CardAnswer.GOOD,
                )
            )
            after = int(
                col.db.scalar("select count(*) from revlog where cid = ?", card_a.id) or 0
            )
            if after - before != 1:
                raise AssertionError(
                    f"expected exactly one new review entry for A, got {after - before}"
                )

            next_top = queued_card(col)
            if int(next_top.card.id) != card_b.id:
                raise AssertionError("learning card B was not returned next by the scheduler")

            return {
                "success": True,
                "ankiVersion": anki.buildinfo.version,
                "collectionPath": str(collection_path),
                "collectionWasDisposable": True,
                "cardAReviewEntriesAdded": after - before,
                "learningCardReturnedNext": True,
                "learningCardDueAt": learning_due_at,
                "stepMinutes": step_minutes,
            }
        finally:
            col.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step-minutes", type=float, default=0.05)
    args = parser.parse_args()
    print(json.dumps(run_spike(args.step_minutes), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
