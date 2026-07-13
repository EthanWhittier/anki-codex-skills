import type { SimplifiedCard } from "@/mcp/types/anki.types";
import {
  compactRenderedHtml,
  compactRenderedReviewCard,
  compactRenderedReviewCardWithMetrics,
} from "../rendered-card-content.utils";

const makeCard = (
  front: string,
  back: string,
  overrides: Partial<SimplifiedCard> = {},
): SimplifiedCard => ({
  cardId: 123,
  front,
  back,
  deckName: "Logic",
  modelName: "Basic",
  due: 1,
  interval: 0,
  factor: 2500,
  ...overrides,
});

describe("rendered card content compaction", () => {
  it("removes repeated template CSS and FrontSide content", () => {
    const css = `
      .card { font-family: arial; font-size: 20px; text-align: center; color: black; }
      .question { margin: 2rem; padding: 1rem; border: 1px solid #ccc; }
      .answer { color: #164; background: #efe; }
    `.repeat(12);
    const front = `<style>${css}</style><div class="question">What follows from P → Q and P?</div>`;
    const back = `<style>${css}</style><div class="question">What follows from P → Q and P?</div><hr><div class="answer">Q</div>`;
    const compacted = compactRenderedReviewCard(makeCard(front, back));

    expect(compacted.front).toBe("What follows from P → Q and P?");
    expect(compacted.back).toBe("Q");
    expect(compacted.front.length + compacted.back.length).toBeLessThanOrEqual(
      (front.length + back.length) * 0.1,
    );
    expect(JSON.stringify(compacted)).not.toMatch(/\.card|<style/);
  });

  it("preserves readable blocks, lists, inline text, tables, and entities", () => {
    const html = `
      <h2>A &amp; B</h2>
      <p>First <em>important</em> point.&nbsp;Next.</p>
      <ul><li>One</li><li>Two</li></ul>
      <table><tr><td>P</td><td>Q</td></tr><tr><td>T</td><td>F</td></tr></table>
    `;

    expect(compactRenderedHtml(html)).toBe(
      "A & B\n\nFirst important point. Next.\n\nOne\n\nTwo\n\nP | Q\n\nT | F",
    );
  });

  it("preserves rendered cloze semantics", () => {
    expect(
      compactRenderedReviewCard(
        makeCard(
          'Water is <span class="cloze">[...]</span>.',
          'Water is <span class="cloze">H₂O</span>.',
        ),
      ),
    ).toMatchObject({
      front: "Water is [...].",
      back: "Water is H₂O.",
    });
  });

  it("preserves TeX source and plain-text line structure", () => {
    const content = String.raw`Schema: codex-generative-exercise/v1
Prompt: Prove \(A \land B \to A\).
Constraints:
- Use natural deduction.
- Name each rule.`;

    expect(
      compactRenderedHtml(
        String.raw`<div>For \(x &lt; y\), show \(x^2 &le; y^2\).</div>`,
      ),
    ).toBe(String.raw`For \(x < y\), show \(x^2 ≤ y^2\).`);
    expect(compactRenderedHtml(content)).toBe(content);
  });

  it("keeps only minimal image markup and preserves audio markers", () => {
    const html = `
      <div>Identify this:</div>
      <img class="large" style="width: 900px" onclick="bad()" src="logic &amp; map.png" width="900">
      <div>[sound:pronunciation.mp3]</div>
    `;

    expect(compactRenderedHtml(html)).toBe(
      'Identify this:\n<img src="logic &amp; map.png">\n[sound:pronunciation.mp3]',
    );
  });

  it.each(["codex-generative-exercise/v1", "codex-open-response-exercise/v1"])(
    "preserves the %s schema marker exactly",
    (schema) => {
      const front = `<style>.hidden { display: none; }</style><section>Schema: ${schema}</section><section>Rubric: explain the inference.</section>`;
      const compacted = compactRenderedReviewCard(
        makeCard(front, "<div>Reference answer</div>", {
          modelName: "Codex Generative Exercise",
        }),
      );

      expect(compacted.front).toContain(`Schema: ${schema}`);
      expect(compacted.front).toContain("Rubric: explain the inference.");
    },
  );

  it("does not truncate long legitimate content", () => {
    const contract = Array.from(
      { length: 250 },
      (_, index) => `Criterion ${index + 1}: preserve this exact requirement.`,
    ).join("\n");

    const compacted = compactRenderedHtml(contract);
    expect(compacted).toBe(contract);
    expect(compacted).toContain(
      "Criterion 250: preserve this exact requirement.",
    );
  });

  it("drops style, script, head, and template subtrees from malformed HTML", () => {
    const html = `
      <head><title>leak title</title><style>.secret { color: red; }</style></head>
      <div>Visible before</div>
      <script>window.stolen = "secret";</script>
      <template><p>template-only metadata</p></template>
      <div><b>Visible after
    `;

    const compacted = compactRenderedHtml(html);
    expect(compacted).toBe("Visible before\n\nVisible after");
    expect(compacted).not.toMatch(/secret|window|template-only|leak title/);
  });

  it("decodes named, decimal, and hexadecimal entities", () => {
    expect(compactRenderedHtml("&quot;A&amp;B&quot; &#62; &#x3C; &copy;")).toBe(
      '"A&B" > < ©',
    );
  });

  it("removes only one exact leading front occurrence", () => {
    expect(
      compactRenderedReviewCard(
        makeCard("Question", "Question\nQuestion\nAnswer"),
      ).back,
    ).toBe("Question\nAnswer");
    expect(
      compactRenderedReviewCard(makeCard("Question", "Intro\nQuestion\nAnswer"))
        .back,
    ).toBe("Intro\nQuestion\nAnswer");
    expect(
      compactRenderedReviewCard(makeCard("Question", "Question?\nAnswer")).back,
    ).toBe("Question?\nAnswer");
  });

  it("retains a back that would become empty and reports content-free metrics", () => {
    const result = compactRenderedReviewCardWithMetrics(
      makeCard("<p>Same</p>", "<div>Same</div>"),
    );

    expect(result.card.back).toBe("Same");
    expect(result.metrics.frontPrefixRemoved).toBe(false);
    expect(result.metrics.frontPrefixRemovalWouldEmptyBack).toBe(true);
    expect(result.metrics).toMatchObject({
      rawFrontChars: 11,
      compactFrontChars: 4,
      rawBackChars: 15,
      compactBackChars: 4,
    });
  });
});
