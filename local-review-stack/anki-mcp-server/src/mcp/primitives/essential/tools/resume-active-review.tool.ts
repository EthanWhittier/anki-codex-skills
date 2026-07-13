import { Injectable } from "@nestjs/common";
import { Tool } from "@rekog/mcp-nest";
import type { Context } from "@rekog/mcp-nest";
import { z } from "zod";
import {
  AnkiConnectClient,
  AnkiConnectError,
} from "@/mcp/clients/anki-connect.client";
import { ChatReviewRecoveryStore } from "@/mcp/services/chat-review-recovery.store";
import type { ChatReviewNextResponse } from "@/mcp/types/anki.types";
import { createErrorResponse } from "@/mcp/utils/anki.utils";
import { compactRenderedReviewCard } from "@/mcp/utils/rendered-card-content.utils";

@Injectable()
export class ResumeActiveReviewTool {
  constructor(
    private readonly ankiClient: AnkiConnectClient,
    private readonly recoveryStore: ChatReviewRecoveryStore,
  ) {}

  @Tool({
    name: "resume_active_review",
    description:
      "Explicitly resume a pending local ticketed review after an MCP reconnect. This only re-reads the frozen pending card and never schedules it.",
    parameters: z.object({
      confirm_resume: z
        .literal(true)
        .describe("Must be true after the learner agrees to resume"),
      deck_name: z.string().optional(),
      expected_card_id: z.number().optional(),
    }),
    outputSchema: z.object({
      success: z.boolean(),
      card: z
        .object({
          cardId: z.number(),
          front: z.string(),
          back: z.string(),
          deckName: z.string(),
          modelName: z.string(),
          due: z.number(),
          interval: z.number(),
          factor: z.number(),
        })
        .nullable(),
      total: z.number(),
      message: z.string(),
      reviewSessionId: z.string().nullable(),
      reviewTicket: z.string().nullable(),
      outcomeCode: z.string(),
      recoveryAgeSeconds: z.number().nullable(),
      originatingMcpProcessGone: z.boolean().nullable(),
    }),
    annotations: {
      title: "Resume Active Review",
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
    },
  })
  async resumeActiveReview(
    {
      deck_name,
      expected_card_id,
    }: {
      confirm_resume: true;
      deck_name?: string;
      expected_card_id?: number;
    },
    context: Context,
  ) {
    let sessionId: string | undefined;
    try {
      const capabilities = await this.ankiClient.getChatReviewCapabilities();
      if (
        !capabilities ||
        !capabilities.supportsRecovery ||
        typeof capabilities.generationHash !== "string"
      ) {
        throw new Error(
          "REVIEW_PROTOCOL_UNSUPPORTED: installed AnkiConnect does not support recoverable chat review",
        );
      }
      const identity = {
        endpointHash: this.ankiClient.endpointIdentifierHash,
        generationHash: capabilities.generationHash,
        protocol: capabilities.protocol,
      } as const;
      const entry = await this.recoveryStore.find(identity);
      if (!entry) {
        throw new Error(
          "REVIEW_RECOVERY_NOT_FOUND: no recoverable review exists for this profile/collection",
        );
      }
      sessionId = entry.reviewSessionId;
      if (deck_name && entry.deckName && deck_name !== entry.deckName) {
        throw new Error(
          "REVIEW_DECK_MISMATCH: recoverable review deck differs",
        );
      }
      if (expected_card_id !== undefined && expected_card_id !== entry.cardId) {
        throw new Error(
          "REVIEW_CARD_MISMATCH: recoverable review card differs from the expected card",
        );
      }

      await context.reportProgress({ progress: 40, total: 100 });
      const result = await this.ankiClient.invoke<ChatReviewNextResponse>(
        "chatReviewNext",
        {
          sessionId,
          deckName: entry.deckName ?? undefined,
          includeLearning: true,
          includeNew: true,
        },
      );
      if (!result.ticket || !result.card) {
        await this.recoveryStore.clearSession(sessionId);
        throw new Error(
          "REVIEW_TICKET_EXPIRED: pending review no longer exists",
        );
      }
      if (result.card.cardId !== entry.cardId) {
        throw new Error(
          "REVIEW_CARD_MISMATCH: Anki returned a different pending card",
        );
      }
      if (deck_name && result.card.deckName !== deck_name) {
        throw new Error("REVIEW_DECK_MISMATCH: Anki returned a different deck");
      }
      await this.recoveryStore.save(
        identity,
        sessionId,
        entry.deckName,
        entry.cardId,
        "active",
      );
      await context.reportProgress({ progress: 100, total: 100 });
      return {
        success: true,
        card: compactRenderedReviewCard(result.card),
        total: result.total,
        message: "Pending review resumed without scheduling the card",
        reviewSessionId: sessionId,
        reviewTicket: result.ticket,
        outcomeCode: "REVIEW_RESUMED",
        recoveryAgeSeconds: Math.max(
          0,
          Math.floor((Date.now() - Date.parse(entry.createdAt)) / 1000),
        ),
        originatingMcpProcessGone: this.processIsGone(entry.originPid),
      };
    } catch (error) {
      if (sessionId) {
        if (this.isDefinitiveInvalidation(error)) {
          await this.recoveryStore.clearSession(sessionId);
        } else {
          await this.recoveryStore.markSession(sessionId, "recovery-required");
        }
      }
      return createErrorResponse(error, {
        outcomeCode: "REVIEW_RESUME_FAILED",
        card: null,
        total: 0,
        reviewSessionId: null,
        reviewTicket: null,
        recoveryAgeSeconds: null,
        originatingMcpProcessGone: null,
      });
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

  private isDefinitiveInvalidation(error: unknown): boolean {
    const message =
      error instanceof AnkiConnectError
        ? (error.originalError ?? error.message)
        : error instanceof Error
          ? error.message
          : String(error);
    return [
      "REVIEW_TICKET_EXPIRED",
      "REVIEW_PROFILE_CHANGED",
      "REVIEW_COLLECTION_CHANGED",
    ].some((code) => message.startsWith(code));
  }
}
