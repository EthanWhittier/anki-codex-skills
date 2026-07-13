import { mkdtempSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ChatReviewRecoveryStore } from "../chat-review-recovery.store";

describe("ChatReviewRecoveryStore", () => {
  let filePath: string;
  const identity = {
    endpointHash: "endpoint-hash",
    generationHash: "generation-hash",
    protocol: "chat-review/v1" as const,
  };

  beforeEach(() => {
    const directory = mkdtempSync(join(tmpdir(), "anki-recovery-test-"));
    filePath = join(directory, "private", "chat-review-recovery.json");
    process.env.ANKI_MCP_CHAT_REVIEW_RECOVERY_FILE = filePath;
  });

  afterEach(() => {
    delete process.env.ANKI_MCP_CHAT_REVIEW_RECOVERY_FILE;
  });

  it("creates a private registry containing only minimal recovery metadata", async () => {
    const store = new ChatReviewRecoveryStore();
    await store.save(identity, "full-session-secret", "Logic", 123);

    expect(statSync(join(filePath, "..")).mode & 0o777).toBe(0o700);
    expect(statSync(filePath).mode & 0o777).toBe(0o600);
    const serialized = readFileSync(filePath, "utf8");
    expect(serialized).toContain("full-session-secret");
    expect(serialized).not.toMatch(/ticket|front|back|answer|rating/i);
  });

  it("preserves the latest complete revision across concurrent writers", async () => {
    const first = new ChatReviewRecoveryStore();
    const second = new ChatReviewRecoveryStore();
    await Promise.all([
      first.save(identity, "session-one", "Logic", 1),
      second.save(
        { ...identity, generationHash: "other-generation" },
        "session-two",
        "Logic",
        2,
      ),
    ]);

    expect(await first.find(identity)).toMatchObject({ cardId: 1 });
    expect(
      await first.find({ ...identity, generationHash: "other-generation" }),
    ).toMatchObject({ cardId: 2 });
  });

  it("fails closed on corrupt or unknown-schema state", async () => {
    const store = new ChatReviewRecoveryStore();
    await store.save(identity, "session", "Logic", 1);
    writeFileSync(filePath, "{truncated", { mode: 0o600 });
    await expect(store.find(identity)).rejects.toThrow(
      "REVIEW_RECOVERY_CORRUPT",
    );

    writeFileSync(
      filePath,
      JSON.stringify({ schemaVersion: 99, revision: 1, entries: [] }),
      { mode: 0o600 },
    );
    await expect(store.find(identity)).rejects.toThrow(
      "REVIEW_RECOVERY_SCHEMA",
    );
  });

  it("keeps uncertain sessions and clears only an explicitly matched session", async () => {
    const store = new ChatReviewRecoveryStore();
    await store.save(identity, "session", "Logic", 1);
    await store.markSession("session", "answer-uncertain");
    expect(await store.find(identity)).toMatchObject({
      state: "answer-uncertain",
    });
    await store.clearSession("different-session");
    expect(await store.find(identity)).not.toBeNull();
    await store.clearSession("session");
    expect(await store.find(identity)).toBeNull();
  });
});
