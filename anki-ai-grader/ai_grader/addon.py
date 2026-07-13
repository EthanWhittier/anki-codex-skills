from __future__ import annotations

import html
import logging
from logging.handlers import RotatingFileHandler
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aqt import gui_hooks, mw
from aqt.operations import QueryOp
from aqt.qt import QAction, qconnect
from aqt.utils import showInfo, tooltip

from .openai_client import GradingRequest, grade_answer
from .text import card_context, strip_html


AGAIN_EASE = 1
ANSWER_MESSAGE_PREFIX = "ai_grader_answer:"
SYMBOL_GROUPS = [
    ("Arithmetic", ["+", "−", "±", "∓", "×", "÷", "·", "⋅", "√", "∛", "∜", "∞", "≈", "≠", "≡"]),
    ("Relations", ["=", "<", ">", "≤", "≥", "≪", "≫", "∝", "∼", "≅", "≃", "≜", "→", "←", "↔", "⇒", "⇔"]),
    ("Sets", ["∈", "∉", "∋", "∌", "⊂", "⊆", "⊄", "⊃", "⊇", "∪", "∩", "∅", "∖", "ℕ", "ℤ", "ℚ", "ℝ", "ℂ"]),
    ("Logic & quantifiers", ["¬", "∧", "∨", "⊕", "⊤", "⊥", "∀", "∃", "∄", "∴", "∵", "⊢", "⊨"]),
    ("Divisibility", ["∣", "∤", "∥", "∦", "gcd", "lcm", "mod", "≡ mod"]),
    ("Calculus", ["Δ", "∂", "∇", "∫", "∬", "∭", "∮", "lim", "d/dx", "dy/dx"]),
    ("Sup/Sub", ["²", "³", "ⁿ", "⁻¹", "₀", "₁", "₂", "ₙ", "ₓ", "₊", "₋"]),
    ("Greek", ["α", "β", "γ", "δ", "ε", "θ", "λ", "μ", "π", "ρ", "σ", "τ", "φ", "χ", "ψ", "ω", "Ω", "Σ", "Π"]),
]


@dataclass(frozen=True)
class AddonConfig:
    openai_api_key: str
    model: str
    fallback_model: str
    auto_grade_typed_answers: bool
    enable_embedded_answer_box: bool
    auto_apply_grade: bool
    auto_answer_delay_ms: int
    include_note_fields: bool
    enable_local_log: bool
    local_log_max_bytes: int
    local_log_backup_count: int
    allow_grading_without_reference: bool
    deck_instructions: dict[str, str]
    grader_notes_field_names: list[str]


_pending_card_ids: set[int] = set()
_embedded_answers: dict[int, str] = {}
_missing_key_warned = False
_logger: logging.Logger | None = None


def initialize() -> None:
    if mw is None:
        return

    gui_hooks.reviewer_did_show_answer.append(_on_reviewer_did_show_answer)
    gui_hooks.reviewer_did_answer_card.append(_on_reviewer_did_answer_card)
    gui_hooks.card_will_show.append(_on_card_will_show)
    gui_hooks.webview_did_receive_js_message.append(_on_webview_message)
    _install_menu_action()
    mw.addonManager.set_config_help_action(__name__, _config_help)


def _install_menu_action() -> None:
    if mw is None:
        return

    action = QAction("AI Grade Current Answer Now", mw)
    qconnect(action.triggered, _manual_grade_current_answer)
    mw.form.menuTools.addAction(action)


def _on_reviewer_did_show_answer(card: Any) -> None:
    config = _load_config()
    if not config.auto_grade_typed_answers:
        return

    reviewer = getattr(mw, "reviewer", None)
    if reviewer is None or getattr(reviewer, "card", None) is None:
        return

    if getattr(reviewer.card, "id", None) != getattr(card, "id", None):
        return

    _start_grading(reviewer, config, auto_started=True)


def _manual_grade_current_answer() -> None:
    config = _load_config()
    reviewer = getattr(mw, "reviewer", None)
    if reviewer is None or getattr(reviewer, "card", None) is None:
        showInfo("No review card is currently active.")
        return

    if getattr(reviewer, "state", None) != "answer":
        showInfo("Show the answer first, then run AI grading.")
        return

    _start_grading(reviewer, config, auto_started=False)


def _start_grading(reviewer: Any, config: AddonConfig, *, auto_started: bool) -> None:
    global _missing_key_warned

    card = reviewer.card
    card_id = int(card.id)
    typed_answer = _learner_answer_for_card(reviewer, card_id)
    reference_answer = _reference_answer_for_card(reviewer)

    if not typed_answer:
        if not auto_started:
            showInfo("Type an answer in the AI answer box or use an Anki typed-answer card first.")
        return

    if not reference_answer and not config.allow_grading_without_reference:
        if not auto_started:
            showInfo(
                "The add-on could not find answer text to grade against. "
                "Enable allow_grading_without_reference to grade from the prompt and model knowledge."
            )
        return

    if card_id in _pending_card_ids:
        return

    if not config.openai_api_key:
        if auto_started:
            if not _missing_key_warned:
                tooltip("AI Grader needs an OpenAI API key in the add-on config.")
                _missing_key_warned = True
        else:
            showInfo("Add your OpenAI API key in Tools > Add-ons > AI Typed Answer Grader > Config.")
        return

    context = card_context(
        card,
        typed_answer=typed_answer,
        reference_answer=reference_answer,
        include_note_fields=config.include_note_fields,
        deck_instructions=config.deck_instructions,
        grader_notes_field_names=config.grader_notes_field_names,
    )
    request = GradingRequest(
        api_key=config.openai_api_key,
        model=config.model,
        fallback_model=config.fallback_model,
        prompt_text=context.prompt_text,
        reference_answer=context.reference_answer,
        learner_answer=context.learner_answer,
        deck_instructions=context.deck_instructions,
        grader_notes=context.grader_notes,
        note_fields=context.note_fields,
    )

    _pending_card_ids.add(card_id)

    def op(_collection: Any) -> dict[str, Any]:
        return grade_answer(request)

    def success(result: dict[str, Any]) -> None:
        _pending_card_ids.discard(card_id)
        _log_grading_result(card_id, result, config)
        _apply_grading_result(reviewer, card_id, result, config)

    def failure(error: Exception) -> None:
        _pending_card_ids.discard(card_id)
        if auto_started:
            tooltip(f"AI grading failed: {error}")
        else:
            showInfo(f"AI grading failed:\n\n{error}\n\n{traceback.format_exc()}")

    QueryOp(parent=mw, op=op, success=success).failure(failure).without_collection().with_progress(
        "AI grading..."
    ).run_in_background()


def _apply_grading_result(
    reviewer: Any,
    card_id: int,
    result: dict[str, Any],
    config: AddonConfig,
) -> None:
    current_card = getattr(reviewer, "card", None)
    if current_card is None or int(current_card.id) != card_id:
        return

    if getattr(reviewer, "state", None) != "answer":
        return

    outcome = result.get("recommendedOutcome")
    audit_summary = (result.get("auditSummary") or "").strip()
    confidence = result.get("confidence")

    if outcome == "good":
        ease = _good_ease(reviewer)
        message = _format_tooltip("Good", confidence, "")
    else:
        ease = AGAIN_EASE
        message = _format_tooltip("Again", confidence, audit_summary)

    tooltip(message)
    typed_answer = _learner_answer_for_card(reviewer, card_id)
    _show_verdict_panel(reviewer, outcome, audit_summary, typed_answer)

    if not config.auto_apply_grade:
        return

    def answer_if_still_current() -> None:
        current = getattr(reviewer, "card", None)
        if current is None or int(current.id) != card_id:
            return
        if getattr(reviewer, "state", None) != "answer":
            return
        reviewer._answerCard(ease)

    delay = max(0, min(config.auto_answer_delay_ms, 10000))
    mw.progress.single_shot(delay, answer_if_still_current)


def _show_verdict_panel(
    reviewer: Any,
    outcome: str,
    audit_summary: str,
    typed_answer: str,
) -> None:
    is_good = outcome == "good"
    icon = "✓" if is_good else "×"
    label = "Good" if is_good else "Again"
    color = "#0f8a3b" if is_good else "#b42318"
    reason = f"""<div class="ai-grader-feedback-reason">{html.escape(audit_summary)}</div>""" if audit_summary else ""
    answer_html = html.escape(typed_answer).replace("\n", "<br>")

    panel = f"""
<style>
  #ai-grader-recommendation {{
    box-sizing: border-box;
    width: min(100% - 220px, 780px);
    max-width: 780px;
    margin: 34px auto 0;
    padding-top: 28px;
    border-top: 1px solid #e3e3e3;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Segoe UI", Arial, sans-serif;
    text-align: center;
  }}
  .ai-grader-review-stack {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 26px;
    width: 100%;
    margin-top: 28px;
  }}
  .ai-grader-user-answer {{
    box-sizing: border-box;
    width: min(100%, 620px);
    margin: 0 auto;
    padding: 0;
    color: #808080;
    font-size: 16px;
    line-height: 1.42;
    text-align: center;
  }}
  .ai-grader-eyebrow {{
    display: inline;
    color: #8a8a8a;
  }}
  .ai-grader-feedback {{
    box-sizing: border-box;
    width: 100%;
    max-width: 620px;
    margin: 0 auto;
    padding: 0;
    border-left: 0;
    color: #111111;
    font-size: 20px;
    line-height: 1.46;
    text-align: center;
  }}
  .ai-grader-feedback-title {{
    display: inline-flex;
    align-items: center;
    gap: 10px;
    margin: 0;
    color: #111111;
    font-size: 21px;
    font-weight: 650;
    line-height: 1.25;
  }}
  .ai-grader-feedback-icon {{
    color: {color};
    font-size: 24px;
    font-weight: 800;
    line-height: 1;
  }}
  .ai-grader-feedback-reason {{
    max-width: 620px;
    margin: 26px auto 0;
    color: #444444;
    font-size: 17px;
    line-height: 1.45;
  }}
  @media (max-width: 720px) {{
    #ai-grader-recommendation {{
      width: min(100% - 48px, 740px);
      margin-top: 30px;
      padding-top: 24px;
    }}
  }}
</style>
<div class="ai-grader-user-answer">
  <span class="ai-grader-eyebrow">Your answer:</span> {answer_html}
</div>
<div class="ai-grader-review-stack">
  <div class="ai-grader-feedback">
    <div class="ai-grader-feedback-title"><span class="ai-grader-feedback-icon">{icon}</span>{label}</div>
    {reason}
  </div>
</div>
"""
    reviewer.web.eval(
        "(() => {"
        "const el = document.getElementById('ai-grader-recommendation');"
        f"if (el) {{ el.innerHTML = {html_js(panel)}; }}"
        "})();"
    )


def _learner_answer_for_card(reviewer: Any, card_id: int) -> str:
    typed_answer = (getattr(reviewer, "typedAnswer", None) or "").strip()
    if typed_answer:
        return typed_answer
    return (_embedded_answers.get(card_id) or "").strip()


def _reference_answer_for_card(reviewer: Any) -> str:
    type_correct = (getattr(reviewer, "typeCorrect", None) or "").strip()
    if type_correct:
        return type_correct

    try:
        return strip_html(reviewer.card.answer())
    except Exception:
        return ""


def _good_ease(reviewer: Any) -> int:
    try:
        if reviewer.mw.col.sched.answerButtons(reviewer.card) == 2:
            return 2
    except Exception:
        pass
    return 3


def _format_tooltip(label: str, confidence: Any, audit_summary: str) -> str:
    try:
        confidence_text = f"{float(confidence):.0%}"
    except Exception:
        confidence_text = "unknown confidence"

    if audit_summary:
        return f"AI graded: {label} ({confidence_text}) - {audit_summary}"
    return f"AI graded: {label} ({confidence_text})"


def _log_grading_result(card_id: int, result: dict[str, Any], config: AddonConfig) -> None:
    if not config.enable_local_log:
        return

    logger = _grading_logger(config)
    if logger is None:
        return

    metadata = result.get("_ai_grader_metadata") or {}
    usage = metadata.get("usage") or {}
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    logger.info(
        "[grading] token usage model=%s cardId=%s inputTokens=%s outputTokens=%s "
        "totalTokens=%s cachedInputTokens=%s reasoningTokens=%s outcome=%s confidence=%s responseId=%s",
        metadata.get("model", ""),
        card_id,
        usage.get("input_tokens", ""),
        usage.get("output_tokens", ""),
        usage.get("total_tokens", ""),
        input_details.get("cached_tokens", ""),
        output_details.get("reasoning_tokens", ""),
        result.get("recommendedOutcome", ""),
        result.get("confidence", ""),
        metadata.get("response_id", ""),
    )


def _grading_logger(config: AddonConfig) -> logging.Logger | None:
    global _logger

    if _logger is not None:
        return _logger

    log_path = _local_log_path()
    if log_path is None:
        return None

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_path,
            maxBytes=max(1024, config.local_log_max_bytes),
            backupCount=max(0, config.local_log_backup_count),
            encoding="utf-8",
        )
    except Exception:
        return None

    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger = logging.getLogger("ai_grader")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for existing_handler in list(logger.handlers):
        if getattr(existing_handler, "_ai_grader_handler", False):
            logger.removeHandler(existing_handler)
            existing_handler.close()
    handler._ai_grader_handler = True
    logger.addHandler(handler)
    _logger = logger
    return _logger


def _local_log_path() -> Path | None:
    try:
        profile_folder = Path(mw.pm.profileFolder())
    except Exception:
        return None
    return profile_folder / "ai_grader.log"


def _on_reviewer_did_answer_card(reviewer: Any, card: Any, ease: int) -> None:
    card_id = int(card.id)
    _pending_card_ids.discard(card_id)
    _embedded_answers.pop(card_id, None)


def _on_card_will_show(html_text: str, card: Any, context: str) -> str:
    if not _has_front_back_fields(card):
        return html_text

    if context == "reviewAnswer":
        config = _load_config()
        if config.enable_embedded_answer_box or config.auto_grade_typed_answers:
            return html_text + _answer_recommendation_placeholder()
        return html_text

    if context != "reviewQuestion":
        return html_text

    config = _load_config()
    if not config.enable_embedded_answer_box:
        return html_text

    try:
        if "[[type:" in card.question():
            return html_text
    except Exception:
        pass

    card_id = int(card.id)
    _embedded_answers.pop(card_id, None)

    return html_text + _embedded_answer_box(card_id)


def _has_front_back_fields(card: Any) -> bool:
    try:
        note_type = card.note_type()
    except Exception:
        try:
            note_type = card.note().model()
        except Exception:
            return False

    fields = note_type.get("flds") or []
    field_names = {
        str(field.get("name", "")).strip().casefold()
        for field in fields
        if isinstance(field, dict)
    }
    return {"front", "back"}.issubset(field_names)


def _embedded_answer_box(card_id: int) -> str:
    placeholder = html.escape("Type your answer here, then show the answer")
    return f"""
<style>
  #ai-grader-answer-wrap {{
    --ai-answer-surface: #ffffff;
    --ai-answer-panel: #f7f7f8;
    --ai-answer-text: #171717;
    --ai-answer-muted: #686868;
    --ai-answer-border: #dedede;
    --ai-answer-hover: #ededf0;
    box-sizing: border-box;
    width: min(calc(100% - 220px), 780px);
    max-width: 780px;
    margin: 7rem auto 0;
    color: var(--ai-answer-text);
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Segoe UI", Arial, sans-serif;
  }}
  body.nightMode #ai-grader-answer-wrap,
  body.night_mode #ai-grader-answer-wrap {{
    --ai-answer-surface: #242424;
    --ai-answer-panel: #2c2c2e;
    --ai-answer-text: #f5f5f5;
    --ai-answer-muted: #b7b7b7;
    --ai-answer-border: #48484a;
    --ai-answer-hover: #3a3a3c;
  }}
  #ai-grader-answer {{
    box-sizing: border-box;
    display: block;
    width: 100%;
    height: 124px;
    min-height: 124px;
    max-height: 124px;
    padding: 24px 28px;
    border: 1px solid var(--ai-answer-border);
    border-radius: 20px;
    outline: none;
    resize: none;
    overflow: auto;
    background: var(--ai-answer-surface);
    color: var(--ai-answer-text);
    font: 19px/1.4 -apple-system, BlinkMacSystemFont, "SF Pro Text", Arial, sans-serif;
    box-shadow: 0 1px 2px rgba(0, 0, 0, .03);
    transition: border-color 140ms ease, box-shadow 140ms ease;
  }}
  #ai-grader-answer:focus {{
    border-color: #858585;
    box-shadow: 0 0 0 3px rgba(127, 127, 127, .12);
  }}
  #ai-grader-answer::placeholder {{
    color: var(--ai-answer-muted);
  }}
  @media (max-width: 720px) {{
    #ai-grader-answer-wrap {{
      width: min(calc(100% - 48px), 780px);
      margin-top: 5rem;
    }}
  }}
</style>
<div id="ai-grader-answer-wrap">
  {_symbol_toolbar()}
  <textarea
    id="ai-grader-answer"
    aria-label="AI grader answer"
    placeholder="{placeholder}"
    rows="3"
    oninput="pycmd('ai_grader_answer:{card_id}:' + encodeURIComponent(this.value));"
  ></textarea>
</div>
"""


def _symbol_toolbar() -> str:
    groups = "\n".join(_symbol_group(label, symbols) for label, symbols in SYMBOL_GROUPS)
    return f"""
  <style>
    #ai-grader-symbols {{
      margin: 0 0 12px;
      text-align: left;
    }}
    #ai-grader-symbols-root {{
      display: flex;
      flex-direction: column;
      align-items: stretch;
    }}
    #ai-grader-symbols-root > summary {{
      display: inline-flex;
      align-items: center;
      align-self: flex-start;
      order: 2;
      gap: 7px;
      cursor: pointer;
      padding: 7px 11px;
      border: 1px solid var(--ai-answer-border);
      border-radius: 9px;
      list-style: none;
      user-select: none;
      background: var(--ai-answer-surface);
      color: var(--ai-answer-muted);
      font-size: 13px;
      font-weight: 600;
      line-height: 1;
      transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
    }}
    #ai-grader-symbols-root > summary::-webkit-details-marker {{
      display: none;
    }}
    #ai-grader-symbols-root > summary:hover,
    #ai-grader-symbols-root[open] > summary {{
      border-color: #a8a8aa;
      background: var(--ai-answer-hover);
      color: var(--ai-answer-text);
    }}
    .ai-grader-symbol-mark {{
      color: var(--ai-answer-text);
      font-family: Georgia, "Times New Roman", serif;
      font-size: 16px;
      font-weight: 500;
    }}
    .ai-grader-symbol-chevron {{
      display: inline-block;
      font-size: 10px;
      transition: transform 150ms ease;
    }}
    #ai-grader-symbols-root[open] .ai-grader-symbol-chevron {{
      transform: rotate(180deg);
    }}
    #ai-grader-symbol-groups {{
      box-sizing: border-box;
      order: 1;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 16px 22px;
      width: 100%;
      max-height: min(42vh, 400px);
      margin: 10px 0 14px;
      padding: 17px 18px 18px;
      border: 1px solid var(--ai-answer-border);
      border-radius: 16px;
      overflow-y: auto;
      overscroll-behavior: contain;
      scrollbar-gutter: stable;
      background: var(--ai-answer-panel);
    }}
    #ai-grader-symbols-root:not([open]) > #ai-grader-symbol-groups {{
      display: none;
    }}
    .ai-grader-symbol-group-label {{
      margin: 0 0 7px 2px;
      color: var(--ai-answer-muted);
      font-size: 10px;
      font-weight: 700;
      letter-spacing: .075em;
      line-height: 1.2;
      text-transform: uppercase;
    }}
    .ai-grader-symbol-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
    }}
    .ai-grader-symbol-button {{
      box-sizing: border-box;
      min-width: 33px;
      height: 31px;
      padding: 0 8px;
      border: 1px solid var(--ai-answer-border);
      border-radius: 8px;
      background: var(--ai-answer-surface);
      color: var(--ai-answer-text);
      font: 15px/1 Georgia, "Times New Roman", serif;
      cursor: pointer;
      transition: background 100ms ease, border-color 100ms ease, transform 100ms ease;
    }}
    .ai-grader-symbol-button:hover,
    .ai-grader-symbol-button:focus-visible {{
      border-color: #9b9b9d;
      background: var(--ai-answer-hover);
      outline: none;
    }}
    .ai-grader-symbol-button:active {{
      transform: scale(.94);
    }}
    @media (max-width: 520px) {{
      #ai-grader-symbol-groups {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
  <div id="ai-grader-symbols" aria-label="Math symbol toolbar">
    <details id="ai-grader-symbols-root">
      <summary aria-label="Show or hide math symbols">
        <span class="ai-grader-symbol-mark" aria-hidden="true">∑</span>
        <span>Math symbols</span>
        <span class="ai-grader-symbol-chevron" aria-hidden="true">⌄</span>
      </summary>
      <div
        id="ai-grader-symbol-groups"
        onclick="
          const button = event.target.closest('.ai-grader-symbol-button');
          if (!button) return;
          const textarea = document.getElementById('ai-grader-answer');
          if (!textarea) return;
          const symbol = button.dataset.symbol || '';
          const start = textarea.selectionStart || 0;
          const end = textarea.selectionEnd || start;
          const value = textarea.value || '';
          textarea.value = value.slice(0, start) + symbol + value.slice(end);
          const next = start + symbol.length;
          textarea.focus();
          textarea.setSelectionRange(next, next);
          textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
        "
      >
        {groups}
      </div>
    </details>
  </div>
"""


def _symbol_group(label: str, symbols: list[str]) -> str:
    buttons = "\n".join(
        f"""<button type="button" class="ai-grader-symbol-button" data-symbol="{html.escape(symbol, quote=True)}" title="Insert {html.escape(symbol)}" aria-label="Insert {html.escape(symbol)}" onmousedown="event.preventDefault()">{html.escape(symbol)}</button>"""
        for symbol in symbols
    )
    return f"""
    <section class="ai-grader-symbol-group" aria-label="{html.escape(label)} symbols">
      <div class="ai-grader-symbol-group-label">{html.escape(label)}</div>
      <div class="ai-grader-symbol-list">
        {buttons}
      </div>
    </section>
"""


def _answer_recommendation_placeholder() -> str:
    return """
<div id="ai-grader-recommendation" style="margin-top: 34px;"></div>
"""


def html_js(value: str) -> str:
    import json

    return json.dumps(value)


def _on_webview_message(
    handled_result: tuple[bool, Any], message: str, context: Any
) -> tuple[bool, Any]:
    if not message.startswith(ANSWER_MESSAGE_PREFIX):
        return handled_result

    try:
        _, raw_card_id, encoded_answer = message.split(":", 2)
        _embedded_answers[int(raw_card_id)] = _percent_decode(encoded_answer)
    except Exception:
        return (True, None)

    return (True, None)


def _percent_decode(value: str) -> str:
    from urllib.parse import unquote_plus

    return unquote_plus(value)


def _load_config() -> AddonConfig:
    raw = mw.addonManager.getConfig(__name__) or {}
    return AddonConfig(
        openai_api_key=str(raw.get("openai_api_key", "")).strip(),
        model=str(raw.get("model", "gpt-5.4-mini")).strip() or "gpt-5.4-mini",
        fallback_model=str(raw.get("fallback_model", "gpt-5.4-mini")).strip() or "gpt-5.4-mini",
        auto_grade_typed_answers=bool(raw.get("auto_grade_typed_answers", True)),
        enable_embedded_answer_box=bool(raw.get("enable_embedded_answer_box", True)),
        auto_apply_grade=bool(raw.get("auto_apply_grade", False)),
        auto_answer_delay_ms=int(raw.get("auto_answer_delay_ms", 1200)),
        include_note_fields=bool(raw.get("include_note_fields", True)),
        enable_local_log=bool(raw.get("enable_local_log", True)),
        local_log_max_bytes=int(raw.get("local_log_max_bytes", 262144)),
        local_log_backup_count=int(raw.get("local_log_backup_count", 0)),
        allow_grading_without_reference=bool(raw.get("allow_grading_without_reference", True)),
        deck_instructions={
            str(key): str(value)
            for key, value in dict(raw.get("deck_instructions", {})).items()
            if str(value).strip()
        },
        grader_notes_field_names=[
            str(value)
            for value in list(
                raw.get(
                    "grader_notes_field_names",
                    ["AI Grader Instructions", "Grader Notes", "Notes"],
                )
            )
        ],
    )


def _config_help() -> str:
    return """
# AI Typed Answer Grader

This add-on grades Anki cards with the same pass/fail policy as the Flashcards app.
For ordinary cards, it adds an answer box to the question side. For native typed-answer
cards, it uses Anki's typed answer.

- `good` means the typed answer is correct enough to pass.
- `again` means the answer is wrong, incomplete, ambiguous, materially imprecise,
  empty, or unusable.

When you show the answer, the add-on grades the learner answer and automatically
answers the card as Again or Good.

Card-specific instructions: add a note field named `AI Grader Instructions`.
Anything in that field will be sent as trusted grader notes.

Deck-specific instructions: put an entry in `deck_instructions`, where the key is
either the deck name or deck id and the value is the grading instruction.

The OpenAI API key is stored in Anki's add-on config. If you share logs or config
files, remove the key first.
"""
