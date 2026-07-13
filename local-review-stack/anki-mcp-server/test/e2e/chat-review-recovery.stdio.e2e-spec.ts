import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { createServer, type Server } from "node:http";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

interface ToolResult {
  content?: Array<{ type: string; text?: string }>;
  structuredContent?: Record<string, unknown>;
}

function decode(result: ToolResult): Record<string, any> {
  if (result.structuredContent) return result.structuredContent;
  const text = result.content?.find((item) => item.type === "text")?.text;
  return text ? JSON.parse(text) : result;
}

function callTool(
  url: string,
  recoveryFile: string,
  toolName: string,
  toolArgs: Record<string, unknown>,
): Promise<Record<string, any>> {
  const args = [
    "@modelcontextprotocol/inspector",
    "--cli",
    "node",
    resolve(__dirname, "../../dist/main-stdio.js"),
    "--transport",
    "stdio",
    "--method",
    "tools/call",
    "--tool-name",
    toolName,
  ];
  for (const [key, value] of Object.entries(toolArgs)) {
    args.push("--tool-arg", `${key}=${String(value)}`);
  }
  return new Promise((resolveResult, reject) => {
    const child = spawn("npx", args, {
      env: {
        ...process.env,
        ANKI_CONNECT_URL: url,
        ANKI_MCP_CHAT_REVIEW_RECOVERY_FILE: recoveryFile,
      },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (data) => (stdout += String(data)));
    child.stderr.on("data", (data) => (stderr += String(data)));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`inspector exited ${code}: ${stderr}`));
        return;
      }
      resolveResult(decode(JSON.parse(stdout)));
    });
  });
}

describe("process-boundary chat-review recovery", () => {
  let server: Server;
  let url: string;
  let pendingSession: string | null;
  let pendingTicket: string | null;
  let answerCount: number;

  beforeAll(async () => {
    pendingSession = null;
    pendingTicket = null;
    answerCount = 0;
    server = createServer((request, response) => {
      let body = "";
      request.on("data", (data) => (body += String(data)));
      request.on("end", () => {
        const call = JSON.parse(body) as {
          action: string;
          params?: Record<string, any>;
        };
        let result: unknown = null;
        let error: string | null = null;
        if (call.action === "chatReviewCapabilities") {
          result = {
            protocol: "chat-review/v1",
            ticketProtocolVersion: "chat-review/v1",
            supportsTickets: true,
            supportsIdempotentReplay: true,
            supportsRecovery: true,
            supportsStatus: true,
            supportsAbandon: true,
            generationHash: "disposable-generation",
            ankiVersion: "26.05",
            ankiVersionVerified: true,
            testedAnkiVersions: ["26.05"],
            fsrs: { enabled: true, scheduler: "fsrs" },
          };
        } else if (call.action === "chatReviewNext") {
          const session = call.params?.sessionId as string;
          if (pendingSession && pendingSession !== session) {
            error = "REVIEW_SESSION_BUSY: another review session is active";
          } else {
            pendingSession = session;
            pendingTicket ??= "disposable-ticket-secret";
            result = {
              success: true,
              ticket: pendingTicket,
              total: 1,
              card: {
                cardId: 123,
                front: "disposable question",
                back: "disposable answer",
                deckName: "Logic",
                modelName: "Basic",
                due: 1,
                interval: 0,
                factor: 2500,
              },
            };
          }
        } else if (call.action === "chatReviewAnswer") {
          if (
            call.params?.sessionId !== pendingSession ||
            call.params?.ticket !== pendingTicket
          ) {
            error = "REVIEW_TICKET_UNKNOWN: ticket mismatch";
          } else {
            answerCount += 1;
            pendingSession = null;
            pendingTicket = null;
            result = {
              success: true,
              replayed: false,
              ratedCard: {
                cardId: 123,
                rating: call.params?.rating,
                ratingDescription: "Good",
              },
              next: { success: true, ticket: null, card: null, total: 0 },
            };
          }
        } else {
          error = "unsupported action";
        }
        response.writeHead(200, { "Content-Type": "application/json" });
        response.end(JSON.stringify({ result, error }));
      });
    });
    await new Promise<void>((resolveListen) =>
      server.listen(0, "127.0.0.1", resolveListen),
    );
    const address = server.address();
    if (!address || typeof address === "string") throw new Error("no address");
    url = `http://127.0.0.1:${address.port}`;
  });

  afterAll(async () => {
    await new Promise<void>((resolveClose) =>
      server.close(() => resolveClose()),
    );
  });

  it("recovers the same card after MCP A exits and rates it exactly once in MCP B", async () => {
    const recoveryFile = join(
      mkdtempSync(join(tmpdir(), "anki-mcp-boundary-")),
      "state",
      "recovery.json",
    );
    const first = await callTool(url, recoveryFile, "get_next_due_card", {
      deck_name: "Logic",
      include_learning: true,
      include_new: true,
    });
    expect(first.card.cardId).toBe(123);

    const replacementGet = await callTool(
      url,
      recoveryFile,
      "get_next_due_card",
      { deck_name: "Logic", include_learning: true, include_new: true },
    );
    expect(replacementGet.outcomeCode).toBe("REVIEW_RECOVERY_AVAILABLE");

    const resumed = await callTool(url, recoveryFile, "resume_active_review", {
      confirm_resume: true,
      deck_name: "Logic",
      expected_card_id: 123,
    });
    expect(resumed.card.cardId).toBe(123);
    expect(resumed.reviewTicket).toBe(first.reviewTicket);

    const rated = await callTool(url, recoveryFile, "rate_card_and_get_next", {
      card_id: 123,
      rating: 3,
      deck_name: "Logic",
      include_learning: true,
      include_new: true,
      review_session_id: resumed.reviewSessionId,
      review_ticket: resumed.reviewTicket,
    });
    expect(rated.success).toBe(true);
    expect(rated.nextCard).toBeNull();
    expect(answerCount).toBe(1);
    const registry = readFileSync(recoveryFile, "utf8");
    expect(registry).not.toContain("disposable-ticket-secret");
    expect(JSON.parse(registry).entries).toEqual([]);
  });
});
