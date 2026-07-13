import { Logger } from "@nestjs/common";
import { parseFragment, type DefaultTreeAdapterMap } from "parse5";
import type { SimplifiedCard } from "@/mcp/types/anki.types";

type HtmlNode = DefaultTreeAdapterMap["node"];
type HtmlElement = DefaultTreeAdapterMap["element"];

const logger = new Logger("RenderedCardContent");

const NON_CONTENT_ELEMENTS = new Set([
  "head",
  "link",
  "meta",
  "noscript",
  "script",
  "style",
  "template",
  "title",
]);

const BLOCK_ELEMENTS = new Set([
  "address",
  "article",
  "aside",
  "blockquote",
  "dd",
  "details",
  "dialog",
  "div",
  "dl",
  "dt",
  "fieldset",
  "figcaption",
  "figure",
  "footer",
  "form",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "header",
  "hgroup",
  "hr",
  "li",
  "main",
  "nav",
  "ol",
  "p",
  "pre",
  "section",
  "summary",
  "table",
  "tbody",
  "tfoot",
  "thead",
  "tr",
  "ul",
]);

export interface RenderedCardCompactionMetrics {
  rawFrontChars: number;
  compactFrontChars: number;
  rawBackChars: number;
  compactBackChars: number;
  frontPrefixRemoved: boolean;
  frontPrefixRemovalWouldEmptyBack: boolean;
}

export interface CompactedRenderedReviewCard {
  card: SimplifiedCard;
  metrics: RenderedCardCompactionMetrics;
}

/**
 * Convert Anki's authoritative rendered HTML into a compact, model-facing form.
 * Scheduling and ticket state are deliberately left outside this transformation.
 */
export function compactRenderedReviewCard(
  card: SimplifiedCard,
): SimplifiedCard {
  return compactRenderedReviewCardWithMetrics(card).card;
}

export function compactRenderedReviewCardWithMetrics(
  card: SimplifiedCard,
): CompactedRenderedReviewCard {
  const front = compactRenderedHtml(card.front);
  const normalizedBack = compactRenderedHtml(card.back);
  const deduplicated = removeExactLeadingFront(normalizedBack, front);
  const compactedCard = {
    ...card,
    front,
    back: deduplicated.back,
  };
  const metrics: RenderedCardCompactionMetrics = {
    rawFrontChars: card.front.length,
    compactFrontChars: compactedCard.front.length,
    rawBackChars: card.back.length,
    compactBackChars: compactedCard.back.length,
    frontPrefixRemoved: deduplicated.removed,
    frontPrefixRemovalWouldEmptyBack: deduplicated.wouldEmptyBack,
  };

  if (process.env.ANKI_MCP_DEBUG_CARD_COMPACTION === "1") {
    logger.debug(`Rendered card compaction ${JSON.stringify(metrics)}`);
  }
  return { card: compactedCard, metrics };
}

export function compactRenderedHtml(html: string): string {
  const fragment = parseFragment(html);
  const output: string[] = [];

  for (const node of fragment.childNodes) {
    appendNode(node, output);
  }

  return normalizeOutput(output.join(""));
}

function appendNode(node: HtmlNode, output: string[]): void {
  if (node.nodeName === "#text" && "value" in node) {
    appendText(node.value, output);
    return;
  }

  if (!("tagName" in node)) {
    return;
  }

  const element = node as HtmlElement;
  const tagName = element.tagName.toLowerCase();
  if (NON_CONTENT_ELEMENTS.has(tagName)) {
    return;
  }

  if (tagName === "br") {
    output.push("\n");
    return;
  }

  if (tagName === "img") {
    const src = element.attrs.find(
      (attribute) => attribute.name === "src",
    )?.value;
    if (src) {
      output.push(`<img src="${escapeAttribute(src)}">`);
    }
    return;
  }

  const isBlock = BLOCK_ELEMENTS.has(tagName);
  if (isBlock) {
    output.push("\n");
  } else if (tagName === "td" || tagName === "th") {
    appendTableCellSeparator(output);
  }

  for (const child of element.childNodes) {
    appendNode(child, output);
  }

  if (isBlock) {
    output.push("\n");
  }
}

function appendText(value: string, output: string[]): void {
  if (!value.trim()) {
    if (/[^\S\r\n]/.test(value)) {
      output.push(" ");
    }
    return;
  }

  output.push(
    value
      .replace(/\r\n?/g, "\n")
      .replace(/[\t\f\v\u00a0 ]+/g, " ")
      .replace(/ *\n */g, "\n"),
  );
}

function appendTableCellSeparator(output: string[]): void {
  const current = output.join("");
  if (current && !/[\n|]\s*$/.test(current)) {
    output.push(" | ");
  }
}

function normalizeOutput(value: string): string {
  return value
    .replace(/[\t\f\v\u00a0 ]+/g, " ")
    .replace(/ *\n */g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function removeExactLeadingFront(
  back: string,
  front: string,
): { back: string; removed: boolean; wouldEmptyBack: boolean } {
  if (
    !front ||
    !back.startsWith(front) ||
    (back.length > front.length && !/^\s/.test(back.slice(front.length)))
  ) {
    return { back, removed: false, wouldEmptyBack: false };
  }

  const remainder = back.slice(front.length).replace(/^\s+/, "");
  if (!remainder) {
    return { back, removed: false, wouldEmptyBack: true };
  }

  return { back: remainder, removed: true, wouldEmptyBack: false };
}

function escapeAttribute(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
