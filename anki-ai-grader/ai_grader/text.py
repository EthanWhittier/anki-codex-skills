from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any


@dataclass(frozen=True)
class CardContext:
    prompt_text: str
    reference_answer: str
    learner_answer: str
    deck_instructions: str
    grader_notes: str
    note_fields: list[tuple[str, str]]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1
        elif tag == "img":
            attr_map = {name: value for name, value in attrs}
            label = attr_map.get("alt") or attr_map.get("src") or "image"
            self.parts.append(f"\n[Image: {label}]\n")
        elif tag in {"br", "div", "p", "li", "tr", "hr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag in {"div", "p", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return normalize_text("".join(self.parts))


def card_context(
    card: Any,
    *,
    typed_answer: str,
    reference_answer: str,
    include_note_fields: bool,
    deck_instructions: dict[str, str],
    grader_notes_field_names: list[str],
) -> CardContext:
    note = card.note()
    note_fields = _note_fields(note) if include_note_fields else []
    deck_name = _deck_name(card)
    deck_instruction = deck_instructions.get(str(card.did), "") or deck_instructions.get(deck_name, "")
    grader_notes = _grader_notes(note_fields, grader_notes_field_names)

    return CardContext(
        prompt_text=strip_html(card.question()),
        reference_answer=strip_html(reference_answer),
        learner_answer=normalize_text(typed_answer),
        deck_instructions=normalize_text(deck_instruction),
        grader_notes=grader_notes,
        note_fields=[
            (name, value)
            for name, value in note_fields
            if name not in set(grader_notes_field_names)
        ],
    )


def strip_html(value: str) -> str:
    without_type_marker = re.sub(r"\[\[type:[^\]]+\]\]", "", value)
    parser = _TextExtractor()
    parser.feed(without_type_marker)
    parser.close()
    return parser.text()


def normalize_text(value: str) -> str:
    value = unescape(value or "")
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _note_fields(note: Any) -> list[tuple[str, str]]:
    try:
        return [(str(name), strip_html(str(value))) for name, value in note.items()]
    except Exception:
        return []


def _grader_notes(note_fields: list[tuple[str, str]], field_names: list[str]) -> str:
    wanted = {name.casefold() for name in field_names}
    values = [value for name, value in note_fields if name.casefold() in wanted and value.strip()]
    return "\n\n".join(values)


def _deck_name(card: Any) -> str:
    try:
        deck = card.col.decks.get(card.did)
        if deck:
            return str(deck.get("name", ""))
    except Exception:
        return ""
    return ""
