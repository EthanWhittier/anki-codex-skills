#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
import urllib.request


def invoke(url: str, action: str, params=None, allow_error=False):
    body = json.dumps({"action": action, "version": 6, "params": params or {}}).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        reply = json.loads(response.read())
    if reply["error"] and not allow_error:
        raise RuntimeError(f"{action}: {reply['error']}")
    return reply


parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:18765")
args = parser.parse_args()

caps = invoke(args.url, "chatReviewCapabilities")["result"]
assert caps["protocol"] == "chat-review/v1" and caps["supportsTickets"]
assert caps["ticketProtocolVersion"] == caps["protocol"]
assert caps["ankiVersionVerified"] is True
assert caps["ankiVersion"] in caps["testedAnkiVersions"]
assert caps["fsrs"]["scheduler"] in ("fsrs", "sm2")
deck = "Disposable Chat Review Smoke"
invoke(args.url, "createDeck", {"deck": deck})
for number in range(1, 13):
    invoke(args.url, "addNote", {"note": {
        "deckName": deck,
        "modelName": "Basic",
        "fields": {"Front": f"Disposable question {number}", "Back": "Disposable answer"},
        "options": {"allowDuplicate": True},
        "tags": ["codex-disposable-smoke"],
    }})

session = "disposable-smoke-session"
first = invoke(args.url, "chatReviewNext", {
    "sessionId": session, "deckName": deck, "includeLearning": True, "includeNew": True,
})["result"]
assert first["ticket"] and first["card"]
ticket = first["ticket"]
card_id = first["card"]["cardId"]
started = time.perf_counter()
answered = invoke(args.url, "chatReviewAnswer", {
    "sessionId": session, "ticket": ticket, "cardId": card_id, "rating": 3, "returnNext": True,
})["result"]
latencies_ms = [(time.perf_counter() - started) * 1000]
assert answered["success"] and not answered["replayed"]
replayed = invoke(args.url, "chatReviewAnswer", {
    "sessionId": session, "ticket": ticket, "cardId": card_id, "rating": 3, "returnNext": True,
})["result"]
assert replayed["success"] and replayed["replayed"]
conflict = invoke(args.url, "chatReviewAnswer", {
    "sessionId": session, "ticket": ticket, "cardId": card_id, "rating": 4, "returnNext": True,
}, allow_error=True)
assert conflict["error"].startswith("REVIEW_TICKET_ALREADY_USED_DIFFERENT_RATING:")
reviews = invoke(args.url, "getReviewsOfCards", {"cards": [card_id]})["result"]
assert len(reviews[str(card_id)]) == 1
next_result = answered["next"]
while next_result and next_result["ticket"]:
    next_ticket = next_result["ticket"]
    next_card_id = next_result["card"]["cardId"]
    started = time.perf_counter()
    next_answer = invoke(args.url, "chatReviewAnswer", {
        "sessionId": session,
        "ticket": next_ticket,
        "cardId": next_card_id,
        "rating": 3,
        "returnNext": True,
    })["result"]
    latencies_ms.append((time.perf_counter() - started) * 1000)
    next_result = next_answer["next"]

median_ms = statistics.median(latencies_ms)
assert median_ms <= 150, f"ticketed rating-plus-next median {median_ms:.1f}ms exceeds 150ms"

print(json.dumps({
    "success": True,
    "protocol": caps["protocol"],
    "ankiVersion": caps["ankiVersion"],
    "ankiVersionVerified": caps["ankiVersionVerified"],
    "fsrs": caps["fsrs"],
    "ticketHash": hashlib.sha256(ticket.encode()).hexdigest()[:12],
    "reviewEntries": 1,
    "idempotentReplay": True,
    "differentRatingConflict": True,
    "ratingPlusNextMedianMs": round(median_ms, 1),
    "ratingPlusNextSamples": len(latencies_ms),
}, indent=2, sort_keys=True))
