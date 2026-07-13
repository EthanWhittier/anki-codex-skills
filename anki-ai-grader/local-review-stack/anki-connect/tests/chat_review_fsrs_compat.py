#!/usr/bin/env python3
"""Disposable FSRS compatibility matrix for the ticketed review protocol."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import anki.buildinfo
from anki.collection import Collection
from anki.cards import Card
from anki.deck_config_pb2 import (
    UPDATE_DECK_CONFIGS_MODE_NORMAL,
    UpdateDeckConfigsRequest,
)
from anki.scheduler.v3 import CardAnswer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plugin import AnkiConnect


RATINGS = (1, 2, 3, 4)
STATES = ("new", "learning", "review", "relearning")


def review_count(col: Collection, card_id: int) -> int:
    return int(col.db.scalar("select count(*) from revlog where cid = ?", card_id) or 0)


def add_note(col: Collection, deck_id: int, label: str) -> int:
    note = col.new_note(col.models.by_name("Basic"))
    note["Front"] = f"disposable FSRS {label}"
    note["Back"] = "disposable answer"
    col.add_note(note, deck_id)
    return int(col.find_cards(f"nid:{note.id}")[0])


def enable_fsrs(col: Collection, deck_id: int, step_minutes: float = 0.01) -> None:
    legacy = col.decks.config_dict_for_deck_id(deck_id)
    legacy["new"]["delays"] = [step_minutes]
    legacy["lapse"]["delays"] = [step_minutes]
    legacy["new"]["perDay"] = 100
    legacy["rev"]["perDay"] = 100
    col.decks.update_config(legacy)

    current = col.decks.get_deck_configs_for_update(deck_id)
    request = UpdateDeckConfigsRequest(
        target_deck_id=deck_id,
        configs=[item.config for item in current.all_config],
        mode=UPDATE_DECK_CONFIGS_MODE_NORMAL,
        card_state_customizer=current.card_state_customizer,
        limits=current.current_deck.limits,
        new_cards_ignore_review_limit=current.new_cards_ignore_review_limit,
        fsrs=True,
        apply_all_parent_limits=current.apply_all_parent_limits,
        fsrs_reschedule=False,
        fsrs_health_check=current.fsrs_health_check,
    )
    col.decks.update_deck_configs(request)
    if not col.decks.get_deck_configs_for_update(deck_id).fsrs:
        raise AssertionError("failed to enable FSRS in disposable collection")


def make_connect(col: Collection, profile: str = "Disposable FSRS Gate") -> AnkiConnect:
    connect = AnkiConnect()
    connect.collection = lambda: col
    connect.scheduler = lambda: col.sched
    connect.window = lambda: SimpleNamespace(pm=SimpleNamespace(name=profile))
    connect.deckNameFromId = lambda deck_id: col.decks.name(deck_id)
    return connect


def queued(col: Collection):
    result = col.sched.get_queued_cards(fetch_limit=1)
    if not result.cards:
        raise AssertionError("scheduler returned no disposable card")
    return result.cards[0]


def answer_queued(col: Collection, rating: CardAnswer.V) -> int:
    top = queued(col)
    card = Card(col, backend_card=top.card)
    card.start_timer()
    col.sched.answer_card(col.sched.build_answer(card=card, states=top.states, rating=rating))
    return int(card.id)


def force_review_due(col: Collection, card_id: int) -> None:
    card = col.get_card(card_id)
    card.type = 2
    card.queue = 2
    card.due = col.sched.today
    col.update_card(card)


def prepare_state(col: Collection, deck_id: int, state: str, label: str) -> int:
    card_id = add_note(col, deck_id, label)
    if state == "new":
        return card_id
    transitioned = answer_queued(col, CardAnswer.AGAIN if state == "learning" else CardAnswer.EASY)
    if transitioned != card_id:
        raise AssertionError("scheduler transitioned an unexpected card")
    if state == "learning":
        return card_id

    force_review_due(col, card_id)
    if state == "review":
        return card_id

    transitioned = answer_queued(col, CardAnswer.AGAIN)
    if transitioned != card_id:
        raise AssertionError("scheduler relearned an unexpected card")
    return card_id


def run_matrix(base: Path) -> list[str]:
    covered: list[str] = []
    for state in STATES:
        for rating in RATINGS:
            path = base / f"matrix-{state}-{rating}.anki2"
            col = Collection(str(path))
            try:
                deck_name = f"FSRS {state} {rating}"
                deck_id = int(col.decks.id(deck_name))
                col.decks.select(deck_id)
                enable_fsrs(col, deck_id)
                preferences = col.get_preferences()
                preferences.scheduling.learn_ahead_secs = 3600
                col.set_preferences(preferences)
                card_id = prepare_state(col, deck_id, state, f"{state}-{rating}")
                card = col.get_card(card_id)
                expected_type = {"new": 0, "learning": 1, "review": 2, "relearning": 3}[state]
                if card.type != expected_type:
                    raise AssertionError(f"expected {state} type {expected_type}, got {card.type}")

                connect = make_connect(col)
                capabilities = connect.chatReviewCapabilities()
                assert capabilities["ankiVersionVerified"] is True
                assert capabilities["ticketProtocolVersion"] == "chat-review/v1"
                assert capabilities["fsrs"] == {"enabled": True, "scheduler": "fsrs"}

                next_result = connect.chatReviewNext(
                    f"matrix-{state}-{rating}", deck_name, True, True
                )
                if next_result["card"]["cardId"] != card_id:
                    raise AssertionError("ticket did not freeze the expected scheduler card")
                frozen = connect.chatReviewPending[f"matrix-{state}-{rating}"]["states"]
                if not frozen.SerializeToString():
                    raise AssertionError("Anki-generated SchedulingStates were not preserved")

                before = review_count(col, card_id)
                answered = connect.chatReviewAnswer(
                    f"matrix-{state}-{rating}",
                    next_result["ticket"],
                    card_id,
                    rating,
                    False,
                )
                after = review_count(col, card_id)
                if after - before != 1:
                    raise AssertionError(f"{state}/{rating} added {after - before} review entries")
                replayed = connect.chatReviewAnswer(
                    f"matrix-{state}-{rating}",
                    next_result["ticket"],
                    card_id,
                    rating,
                    False,
                )
                if not replayed["replayed"] or review_count(col, card_id) != after:
                    raise AssertionError(f"duplicate ticket changed {state}/{rating} scheduling")
                covered.append(f"{state}:{rating}")
            finally:
                col.close()
    return covered


def run_queue_reordering(base: Path) -> None:
    col = Collection(str(base / "queue-reordering.anki2"))
    try:
        deck_name = "FSRS Queue Reordering"
        deck_id = int(col.decks.id(deck_name))
        col.decks.select(deck_id)
        enable_fsrs(col, deck_id, step_minutes=0.05)
        preferences = col.get_preferences()
        preferences.scheduling.learn_ahead_secs = 0
        col.set_preferences(preferences)
        card_ids = {add_note(col, deck_id, "queue-a"), add_note(col, deck_id, "queue-b")}

        learning_id = answer_queued(col, CardAnswer.AGAIN)
        connect = make_connect(col)
        pending = connect.chatReviewNext("queue-reordering", deck_name, True, True)
        pending_id = pending["card"]["cardId"]
        if {learning_id, pending_id} != card_ids:
            raise AssertionError("unexpected cards in queue-reordering fixture")
        learning_card = col.get_card(learning_id)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and int(time.time()) < int(learning_card.due):
            time.sleep(0.02)
        before = review_count(col, pending_id)
        answered = connect.chatReviewAnswer(
            "queue-reordering", pending["ticket"], pending_id, 3, True
        )
        if review_count(col, pending_id) - before != 1:
            raise AssertionError("queue-reordered answer did not add exactly one review entry")
        if answered["next"]["card"]["cardId"] != learning_id:
            raise AssertionError("newly due learning card was not returned next")
    finally:
        col.close()


def run_sync(base: Path, endpoint: str, username: str, password: str) -> None:
    source_path = base / "sync-source.anki2"
    source = Collection(str(source_path))
    try:
        deck_name = "FSRS Local Sync"
        deck_id = int(source.decks.id(deck_name))
        source.decks.select(deck_id)
        enable_fsrs(source, deck_id)
        card_id = add_note(source, deck_id, "sync")
        connect = make_connect(source)
        pending = connect.chatReviewNext("sync", deck_name, True, True)
        connect.chatReviewAnswer("sync", pending["ticket"], card_id, 3, False)
        if review_count(source, card_id) != 1:
            raise AssertionError("sync source does not have exactly one review entry")
        auth = source.sync_login(username, password, endpoint)
        output = source.sync_collection(auth, False)
        if output.required not in (output.NO_CHANGES, output.NORMAL_SYNC):
            source.full_upload_or_download(auth=auth, server_usn=None, upload=True)
        output = source.sync_collection(auth, False)
        if output.required not in (output.NO_CHANGES, output.NORMAL_SYNC):
            raise AssertionError(f"local sync did not settle: {output.required}")
    finally:
        source.close()

    target = Collection(str(base / "sync-target.anki2"))
    try:
        auth = target.sync_login(username, password, endpoint)
        output = target.sync_collection(auth, False)
        if output.required not in (output.NO_CHANGES, output.NORMAL_SYNC):
            target.full_upload_or_download(auth=auth, server_usn=None, upload=False)
        if review_count(target, card_id) != 1:
            raise AssertionError("locally synced target did not preserve exactly one review entry")
        if not target.decks.get_deck_configs_for_update(target.get_card(card_id).did).fsrs:
            raise AssertionError("locally synced target did not preserve FSRS status")
    finally:
        target.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-endpoint", required=True)
    parser.add_argument("--sync-username", default="gate")
    parser.add_argument("--sync-password", default="gatepass")
    parser.add_argument("--candidate-version")
    args = parser.parse_args()

    running = anki.buildinfo.version
    if args.candidate_version:
        if args.candidate_version != running:
            raise SystemExit(
                f"candidate version {args.candidate_version} does not match running Anki {running}"
            )
        AnkiConnect.CHAT_REVIEW_TESTED_ANKI_VERSIONS = tuple(
            sorted(set(AnkiConnect.CHAT_REVIEW_TESTED_ANKI_VERSIONS + (running,)))
        )

    with tempfile.TemporaryDirectory(prefix="anki-chat-review-fsrs-") as tmp:
        base = Path(tmp)
        covered = run_matrix(base)
        run_queue_reordering(base)
        run_sync(base, args.sync_endpoint, args.sync_username, args.sync_password)
        print(
            json.dumps(
                {
                    "success": True,
                    "collectionWasDisposable": True,
                    "ankiVersion": running,
                    "ticketProtocolVersion": AnkiConnect.CHAT_REVIEW_PROTOCOL,
                    "fsrsEnabled": True,
                    "stateRatingCases": covered,
                    "duplicateTickets": True,
                    "exactlyOneReviewLogEntry": True,
                    "queueReordering": True,
                    "localSyncRoundTrip": True,
                },
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
