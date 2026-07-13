import { Injectable } from "@nestjs/common";
import { Tool } from "@rekog/mcp-nest";
import type { Context } from "@rekog/mcp-nest";
import { randomUUID } from "node:crypto";
import { z } from "zod";
import { AnkiConnectClient } from "@/mcp/clients/anki-connect.client";
import type { ChatReviewNextResponse } from "@/mcp/types/anki.types";
import { createErrorResponse } from "@/mcp/utils/anki.utils";
import { compactRenderedReviewCard } from "@/mcp/utils/rendered-card-content.utils";
import { ChatReviewRecoveryStore } from "@/mcp/services/chat-review-recovery.store";
import { GetDueCardsTool } from "./get-due-cards.tool";

/**
 * Tool for retrieving the single next card available in Anki's scheduler queue.
 */
@Injectable()
export class GetNextDueCardTool {
  constructor(
    private readonly ankiClient: AnkiConnectClient,
    private readonly getDueCardsTool: GetDueCardsTool,
    private readonly recoveryStore: ChatReviewRecoveryStore,
  ) {}

  @Tool({
    name: "get_next_due_card",
    description:
      "Retrieve the single next card available for review from Anki. Uses the same visible queue and scheduler ordering as get_due_cards, but returns only one card.",
    parameters: z.object({
      deck_name: z
        .string()
        .optional()
        .describe(
          "Specific deck name to get the next card from. If not specified, gets the next card from all decks",
        ),
      include_learning: z
        .boolean()
        .default(true)
        .describe(
          "Include cards in learning phase (seen but not yet graduated). Default: true",
        ),
      include_new: z
        .boolean()
        .default(false)
        .describe("Include new cards (never seen before). Default: false"),
      review_session_id: z
        .string()
        .optional()
        .describe(
          "Opaque review session returned by a prior call. Keep machine-facing and never show it to the learner.",
        ),
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
      outcomeCode: z.string().optional(),
    }),
    annotations: {
      title: "Get Next Due Card",
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
    },
  })
  async getNextDueCard(
    {
      deck_name,
      include_learning = true,
      include_new = false,
      review_session_id,
    }: {
      deck_name?: string;
      include_learning?: boolean;
      include_new?: boolean;
      review_session_id?: string;
    },
    context: Context,
  ) {
    await context.reportProgress({ progress: 10, total: 100 });
    try {
      const capabilities = await this.ankiClient.getChatReviewCapabilities();
      if (capabilities) {
        if (!capabilities.ankiVersionVerified) {
          throw new Error(
            `ANKI_VERSION_UNVERIFIED: Anki ${capabilities.ankiVersion} has not passed the isolated chat-review compatibility gate`,
          );
        }
        const recoveryEnabled =
          capabilities.supportsRecovery === true &&
          typeof capabilities.generationHash === "string";
        const identity = recoveryEnabled
          ? ({
              endpointHash: this.ankiClient.endpointIdentifierHash,
              generationHash: capabilities.generationHash,
              protocol: capabilities.protocol,
            } as const)
          : null;
        const recoverable = identity
          ? await this.recoveryStore.find(identity)
          : null;
        if (
          recoverable &&
          !review_session_id &&
          !this.recoveryStore.belongsToCurrentProcess(recoverable)
        ) {
          return {
            success: false,
            card: null,
            total: 0,
            message:
              "REVIEW_RECOVERY_AVAILABLE: a previous local review is still pending; use resume_active_review with explicit confirmation",
            reviewSessionId: null,
            reviewTicket: null,
            outcomeCode: "REVIEW_RECOVERY_AVAILABLE",
          };
        }
        if (
          recoverable &&
          review_session_id &&
          review_session_id !== recoverable.reviewSessionId
        ) {
          throw new Error(
            "REVIEW_RECOVERY_CONFLICT: supplied session does not own the active recoverable review",
          );
        }
        const sessionId =
          review_session_id ?? recoverable?.reviewSessionId ?? randomUUID();
        const result = await this.ankiClient.invoke<ChatReviewNextResponse>(
          "chatReviewNext",
          {
            sessionId,
            deckName: deck_name,
            includeLearning: include_learning,
            includeNew: include_new,
          },
        );
        await context.reportProgress({ progress: 100, total: 100 });
        if (identity && result.ticket && result.card) {
          await this.recoveryStore.save(
            identity,
            sessionId,
            deck_name ?? result.card.deckName,
            result.card.cardId,
          );
        } else if (identity) {
          await this.recoveryStore.clearSession(sessionId);
        }
        return {
          success: result.success,
          card: result.card ? compactRenderedReviewCard(result.card) : null,
          total: result.total,
          message: result.card
            ? "Found next due card"
            : "No cards are due for review",
          reviewSessionId: result.ticket ? sessionId : null,
          reviewTicket: result.ticket,
        };
      }

      const result = await this.getDueCardsTool.getNextDueCardData({
        deck_name,
        include_learning,
        include_new,
      });
      await context.reportProgress({ progress: 100, total: 100 });
      if (!result.success) {
        return result;
      }
      return {
        ...result,
        reviewSessionId: null,
        reviewTicket: null,
      };
    } catch (error) {
      return createErrorResponse(error, {
        hint: "Make sure Anki is running and the maintained AnkiConnect add-on is installed",
      });
    }
  }
}
