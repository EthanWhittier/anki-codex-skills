import { Injectable } from "@nestjs/common";
import { Tool } from "@rekog/mcp-nest";
import type { Context } from "@rekog/mcp-nest";
import { z } from "zod";
import { AnkiConnectClient } from "@/mcp/clients/anki-connect.client";
import { ChatReviewRecoveryStore } from "@/mcp/services/chat-review-recovery.store";
import type { ChatReviewStatusResponse } from "@/mcp/types/anki.types";
import { createErrorResponse } from "@/mcp/utils/anki.utils";

@Injectable()
export class ActiveReviewStatusTool {
  constructor(private readonly ankiClient: AnkiConnectClient) {}

  @Tool({
    name: "get_active_review_status",
    description:
      "Read non-secret metadata about Anki's pending chat review. Does not reveal a session ID, ticket, or card answer.",
    parameters: z.object({}),
    outputSchema: z.object({
      success: z.boolean(),
      active: z.boolean(),
      cardId: z.number().nullable(),
      deckName: z.string().nullable(),
      pendingAgeSeconds: z.number().nullable(),
      message: z.string(),
    }),
    annotations: {
      title: "Get Active Review Status",
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
    },
  })
  async getStatus(_input: Record<string, never>, context: Context) {
    try {
      const status =
        await this.ankiClient.invoke<ChatReviewStatusResponse>(
          "chatReviewStatus",
        );
      await context.reportProgress({ progress: 100, total: 100 });
      return {
        success: true,
        active: status.active,
        cardId: status.cardId ?? null,
        deckName: status.deckName ?? null,
        pendingAgeSeconds: status.pendingAgeSeconds ?? null,
        message: status.active
          ? "A pending chat review exists"
          : "No pending chat review exists",
      };
    } catch (error) {
      return createErrorResponse(error, {
        active: false,
        cardId: null,
        deckName: null,
        pendingAgeSeconds: null,
      });
    }
  }
}

@Injectable()
export class AbandonActiveReviewTool {
  constructor(
    private readonly ankiClient: AnkiConnectClient,
    private readonly recoveryStore: ChatReviewRecoveryStore,
  ) {}

  @Tool({
    name: "abandon_active_review",
    description:
      "Explicitly abandon Anki's current pending chat-review ticket without scheduling it. Requires a fresh status match and learner confirmation.",
    parameters: z.object({
      expected_card_id: z.number(),
      confirm_abandon: z.literal(true),
    }),
    outputSchema: z.object({
      success: z.boolean(),
      abandoned: z.boolean(),
      cardId: z.number(),
      message: z.string(),
    }),
    annotations: {
      title: "Abandon Active Review",
      readOnlyHint: false,
      destructiveHint: true,
      idempotentHint: false,
    },
  })
  async abandon(
    { expected_card_id }: { expected_card_id: number; confirm_abandon: true },
    context: Context,
  ) {
    try {
      const status =
        await this.ankiClient.invoke<ChatReviewStatusResponse>(
          "chatReviewStatus",
        );
      if (
        !status.active ||
        status.cardId !== expected_card_id ||
        !status.ownerHash
      ) {
        throw new Error(
          "REVIEW_CARD_MISMATCH: active review does not match the expected card",
        );
      }
      const result = await this.ankiClient.invoke<{
        success: boolean;
        abandoned: boolean;
        cardId: number;
      }>("chatReviewAbandon", {
        generationHash: status.generationHash,
        ownerHash: status.ownerHash,
        expectedCardId: expected_card_id,
        confirm: true,
      });
      const capabilities = await this.ankiClient.getChatReviewCapabilities();
      if (capabilities) {
        const entry = await this.recoveryStore.find({
          endpointHash: this.ankiClient.endpointIdentifierHash,
          generationHash: capabilities.generationHash,
          protocol: capabilities.protocol,
        });
        if (entry) await this.recoveryStore.clearSession(entry.reviewSessionId);
      }
      await context.reportProgress({ progress: 100, total: 100 });
      return {
        ...result,
        message: "Pending review abandoned without scheduling",
      };
    } catch (error) {
      return createErrorResponse(error, {
        abandoned: false,
        cardId: expected_card_id,
      });
    }
  }
}
