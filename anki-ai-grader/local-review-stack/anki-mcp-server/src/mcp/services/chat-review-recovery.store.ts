import { Injectable } from "@nestjs/common";
import { createHash, randomUUID } from "node:crypto";
import {
  closeSync,
  constants,
  existsSync,
  fsyncSync,
  mkdirSync,
  openSync,
  readFileSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

export type ChatReviewRecoveryState =
  | "active"
  | "answer-uncertain"
  | "recovery-required";

export interface ChatReviewRecoveryIdentity {
  endpointHash: string;
  generationHash: string;
  protocol: "chat-review/v1";
}

export interface ChatReviewRecoveryEntry extends ChatReviewRecoveryIdentity {
  reviewSessionId: string;
  deckName: string | null;
  cardId: number;
  createdAt: string;
  lastSuccessAt: string;
  originPid: number;
  processNonce: string;
  sessionHash: string;
  state: ChatReviewRecoveryState;
}

interface RecoveryRegistry {
  schemaVersion: 1;
  revision: number;
  entries: ChatReviewRecoveryEntry[];
}

const PROCESS_NONCE = randomUUID();

function sha256(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

function isEntry(value: unknown): value is ChatReviewRecoveryEntry {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return (
    item.protocol === "chat-review/v1" &&
    typeof item.endpointHash === "string" &&
    typeof item.generationHash === "string" &&
    typeof item.reviewSessionId === "string" &&
    typeof item.deckName !== "undefined" &&
    (item.deckName === null || typeof item.deckName === "string") &&
    Number.isSafeInteger(item.cardId) &&
    typeof item.createdAt === "string" &&
    typeof item.lastSuccessAt === "string" &&
    Number.isInteger(item.originPid) &&
    typeof item.processNonce === "string" &&
    typeof item.sessionHash === "string" &&
    ["active", "answer-uncertain", "recovery-required"].includes(
      String(item.state),
    )
  );
}

@Injectable()
export class ChatReviewRecoveryStore {
  readonly processNonce = PROCESS_NONCE;
  private readonly filePath: string;
  private readonly lockPath: string;

  constructor() {
    this.filePath =
      process.env.ANKI_MCP_CHAT_REVIEW_RECOVERY_FILE ??
      join(
        homedir(),
        "Library",
        "Application Support",
        "anki-mcp",
        "chat-review-recovery.json",
      );
    this.lockPath = `${this.filePath}.lock`;
  }

  static endpointHash(endpoint: string): string {
    return sha256(endpoint);
  }

  static sessionHash(sessionId: string): string {
    return sha256(sessionId).slice(0, 12);
  }

  belongsToCurrentProcess(entry: ChatReviewRecoveryEntry): boolean {
    return (
      entry.originPid === process.pid &&
      entry.processNonce === this.processNonce
    );
  }

  async find(
    identity: ChatReviewRecoveryIdentity,
  ): Promise<ChatReviewRecoveryEntry | null> {
    return this.withLock(() => {
      const registry = this.readRegistry();
      return (
        registry.entries.find((entry) => this.matches(entry, identity)) ?? null
      );
    });
  }

  async findBySession(
    sessionId: string,
  ): Promise<ChatReviewRecoveryEntry | null> {
    return this.withLock(() => {
      const registry = this.readRegistry();
      return (
        registry.entries.find((entry) => entry.reviewSessionId === sessionId) ??
        null
      );
    });
  }

  async save(
    identity: ChatReviewRecoveryIdentity,
    sessionId: string,
    deckName: string | null,
    cardId: number,
    state: ChatReviewRecoveryState = "active",
  ): Promise<ChatReviewRecoveryEntry> {
    return this.withLock(() => {
      const registry = this.readRegistry();
      const previous = registry.entries.find((entry) =>
        this.matches(entry, identity),
      );
      const now = new Date().toISOString();
      const entry: ChatReviewRecoveryEntry = {
        ...identity,
        reviewSessionId: sessionId,
        deckName,
        cardId,
        createdAt: previous?.createdAt ?? now,
        lastSuccessAt: now,
        originPid: previous?.originPid ?? process.pid,
        processNonce: previous?.processNonce ?? this.processNonce,
        sessionHash: ChatReviewRecoveryStore.sessionHash(sessionId),
        state,
      };
      registry.entries = registry.entries.filter(
        (candidate) => !this.matches(candidate, identity),
      );
      registry.entries.push(entry);
      registry.revision += 1;
      this.writeRegistry(registry);
      return entry;
    });
  }

  async markSession(
    sessionId: string,
    state: ChatReviewRecoveryState,
  ): Promise<void> {
    await this.withLock(() => {
      const registry = this.readRegistry();
      const entry = registry.entries.find(
        (candidate) => candidate.reviewSessionId === sessionId,
      );
      if (!entry) return;
      entry.state = state;
      registry.revision += 1;
      this.writeRegistry(registry);
    });
  }

  async clearSession(sessionId: string): Promise<void> {
    await this.withLock(() => {
      const registry = this.readRegistry();
      const remaining = registry.entries.filter(
        (entry) => entry.reviewSessionId !== sessionId,
      );
      if (remaining.length === registry.entries.length) return;
      registry.entries = remaining;
      registry.revision += 1;
      this.writeRegistry(registry);
    });
  }

  private matches(
    entry: ChatReviewRecoveryEntry,
    identity: ChatReviewRecoveryIdentity,
  ): boolean {
    return (
      entry.protocol === identity.protocol &&
      entry.endpointHash === identity.endpointHash &&
      entry.generationHash === identity.generationHash
    );
  }

  private ensureDirectory(): void {
    const directory = dirname(this.filePath);
    mkdirSync(directory, { recursive: true, mode: 0o700 });
    const mode = statSync(directory).mode & 0o777;
    if ((mode & 0o077) !== 0) {
      throw new Error(
        "REVIEW_RECOVERY_PERMISSIONS: recovery directory is not private",
      );
    }
  }

  private readRegistry(): RecoveryRegistry {
    this.ensureDirectory();
    if (!existsSync(this.filePath)) {
      return { schemaVersion: 1, revision: 0, entries: [] };
    }
    const mode = statSync(this.filePath).mode & 0o777;
    if ((mode & 0o077) !== 0) {
      throw new Error(
        "REVIEW_RECOVERY_PERMISSIONS: recovery file is not private",
      );
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(readFileSync(this.filePath, "utf8"));
    } catch {
      throw new Error("REVIEW_RECOVERY_CORRUPT: recovery registry is invalid");
    }
    const registry = parsed as Partial<RecoveryRegistry>;
    if (
      registry.schemaVersion !== 1 ||
      !Number.isSafeInteger(registry.revision) ||
      !Array.isArray(registry.entries) ||
      !registry.entries.every(isEntry)
    ) {
      throw new Error("REVIEW_RECOVERY_SCHEMA: unsupported recovery registry");
    }
    return registry as RecoveryRegistry;
  }

  private writeRegistry(registry: RecoveryRegistry): void {
    this.ensureDirectory();
    const temporary = `${this.filePath}.${process.pid}.${this.processNonce}.tmp`;
    const descriptor = openSync(
      temporary,
      constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY,
      0o600,
    );
    try {
      writeFileSync(
        descriptor,
        `${JSON.stringify(registry, null, 2)}\n`,
        "utf8",
      );
      fsyncSync(descriptor);
    } finally {
      closeSync(descriptor);
    }
    renameSync(temporary, this.filePath);
    const directoryDescriptor = openSync(
      dirname(this.filePath),
      constants.O_RDONLY,
    );
    try {
      fsyncSync(directoryDescriptor);
    } finally {
      closeSync(directoryDescriptor);
    }
  }

  private async withLock<T>(operation: () => T): Promise<T> {
    this.ensureDirectory();
    let descriptor: number | undefined;
    for (let attempt = 0; attempt < 100; attempt += 1) {
      try {
        descriptor = openSync(
          this.lockPath,
          constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY,
          0o600,
        );
        writeFileSync(
          descriptor,
          JSON.stringify({
            pid: process.pid,
            processNonce: this.processNonce,
            createdAt: new Date().toISOString(),
          }),
          "utf8",
        );
        fsyncSync(descriptor);
        break;
      } catch (error) {
        const code = (error as NodeJS.ErrnoException).code;
        if (code !== "EEXIST") throw error;
        try {
          if (Date.now() - statSync(this.lockPath).mtimeMs > 30_000) {
            const owner = JSON.parse(readFileSync(this.lockPath, "utf8")) as {
              pid?: unknown;
            };
            if (
              typeof owner.pid !== "number" ||
              this.processIsGone(owner.pid)
            ) {
              unlinkSync(this.lockPath);
              continue;
            }
          }
        } catch {
          continue;
        }
        await new Promise((resolve) => setTimeout(resolve, 20));
      }
    }
    if (descriptor === undefined) {
      throw new Error("REVIEW_RECOVERY_LOCKED: recovery registry is busy");
    }
    try {
      return operation();
    } finally {
      closeSync(descriptor);
      try {
        unlinkSync(this.lockPath);
      } catch {
        // Another reader will either acquire the lock or reject safely.
      }
    }
  }

  private processIsGone(pid: number): boolean {
    try {
      process.kill(pid, 0);
      return false;
    } catch {
      return true;
    }
  }
}
