import { Injectable, Logger } from "@nestjs/common";
import { Tool } from "@rekog/mcp-nest";
import type { Context } from "@rekog/mcp-nest";
import { z } from "zod";
import { AnkiConnectClient } from "@/mcp/clients/anki-connect.client";
import type { ChatReviewAnswerResponse } from "@/mcp/types/anki.types";
import {
  getRatingDescription,
  createErrorResponse,
} from "@/mcp/utils/anki.utils";
import { ChatReviewRecoveryStore } from "@/mcp/services/chat-review-recovery.store";
import { AnkiConnectError } from "@/mcp/clients/anki-connect.client";

/**
 * Tool for rating a card and updating Anki's scheduling
 */
@Injectable()
export class RateCardTool {
  private readonly logger = new Logger(RateCardTool.name);

  constructor(
    private readonly ankiClient: AnkiConnectClient,
    private readonly recoveryStore: ChatReviewRecoveryStore,
  ) {}

  @Tool({
    name: "rate_card",
    description:
      "Submit the user's chosen rating for a card to update Anki's spaced repetition scheduling. During review sessions, prefer rate_card_and_get_next when the next card should be returned immediately.",
    parameters: z.object({
      card_id: z.number().describe("The ID of the card to rate"),
      rating: z
        .number()
        .min(1)
        .max(4)
        .describe(
          "The user's chosen rating: 1=Again (failed), 2=Hard, 3=Good, 4=Easy",
        ),
      review_session_id: z.string().optional(),
      review_ticket: z.string().optional(),
    }),
    outputSchema: z.object({
      success: z.boolean(),
      cardId: z.number(),
      rating: z.number(),
      ratingDescription: z.string(),
      message: z.string(),
      nextReview: z
        .object({
          interval: z.number(),
          due: z.number(),
          factor: z.number(),
        })
        .nullable(),
      replayed: z.boolean(),
    }),
    annotations: {
      title: "Rate Card",
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
    },
  })
  async rateCard(
    {
      card_id,
      rating,
      review_session_id,
      review_ticket,
    }: {
      card_id: number;
      rating: number;
      review_session_id?: string;
      review_ticket?: string;
    },
    context: Context,
  ) {
    let ticketAnswerAttempted = false;
    try {
      // Validate rating
      if (!Number.isInteger(rating) || rating < 1 || rating > 4) {
        return createErrorResponse(
          new Error(
            "Invalid rating. Must be 1 (Again), 2 (Hard), 3 (Good), or 4 (Easy)",
          ),
          { cardId: card_id, attemptedRating: rating },
        );
      }

      if (
        (review_session_id && !review_ticket) ||
        (!review_session_id && review_ticket)
      ) {
        return createErrorResponse(
          new Error(
            "review_session_id and review_ticket must be provided together",
          ),
          { cardId: card_id, attemptedRating: rating },
        );
      }

      this.logger.log(`Rating card ${card_id} with rating ${rating}`);
      await context.reportProgress({ progress: 25, total: 100 });

      if (review_session_id && review_ticket) {
        const capabilities = await this.ankiClient.getChatReviewCapabilities();
        if (!capabilities) {
          throw new Error(
            "REVIEW_PROTOCOL_UNSUPPORTED: installed AnkiConnect does not support chat-review/v1",
          );
        }
        if (!capabilities.ankiVersionVerified) {
          throw new Error(
            `ANKI_VERSION_UNVERIFIED: Anki ${capabilities.ankiVersion} has not passed the isolated chat-review compatibility gate`,
          );
        }
        ticketAnswerAttempted = true;
        const result = await this.ankiClient.invoke<ChatReviewAnswerResponse>(
          "chatReviewAnswer",
          {
            sessionId: review_session_id,
            ticket: review_ticket,
            cardId: card_id,
            rating,
            returnNext: false,
          },
        );
        if (result.ratedCard.cardId !== card_id) {
          throw new Error(
            "REVIEW_CARD_MISMATCH: ticketed response card mismatch",
          );
        }
        await this.recoveryStore.clearSession(review_session_id);
        await context.reportProgress({ progress: 100, total: 100 });
        return {
          success: result.success,
          cardId: card_id,
          rating,
          ratingDescription: result.ratedCard.ratingDescription,
          message: `Card successfully rated as ${result.ratedCard.ratingDescription}`,
          nextReview: null,
          replayed: result.replayed,
        };
      }

      // Validate the card ID exists before answering. AnkiConnect's
      // `answerCards` returns `true` even for bogus IDs, so we must
      // pre-check with `cardsInfo` (missing cards come back as `{}`).
      const existingInfo = await this.ankiClient.invoke<
        Array<{ cardId?: number }>
      >("cardsInfo", { cards: [card_id] });

      const found =
        existingInfo?.[0] && typeof existingInfo[0].cardId === "number";

      if (!found) {
        return createErrorResponse(
          new Error(
            `Card ID ${card_id} does not exist in the Anki collection. Cannot rate.`,
          ),
          {
            cardId: card_id,
            attemptedRating: rating,
            hint: "Verify the card ID with get_due_cards or findNotes before rating",
          },
        );
      }

      // Convert rating to ease for AnkiConnect
      // AnkiConnect's answerCards expects ease values 1-4
      const answers = [
        {
          cardId: card_id,
          ease: rating,
        },
      ];

      // Submit the rating to Anki
      const result = await this.ankiClient.invoke<boolean>("answerCards", {
        answers,
      });

      if (!result) {
        throw new Error(`Failed to rate card ${card_id}`);
      }

      const ratingDesc = getRatingDescription(rating);

      this.logger.log(`Card ${card_id} rated as ${ratingDesc}`);
      await context.reportProgress({ progress: 75, total: 100 });

      await context.reportProgress({ progress: 100, total: 100 });

      return {
        success: true,
        cardId: card_id,
        rating: rating,
        ratingDescription: ratingDesc,
        message: `Card successfully rated as ${ratingDesc}`,
        nextReview: null,
        replayed: false,
      };
    } catch (error) {
      if (review_session_id && ticketAnswerAttempted) {
        const detail =
          error instanceof AnkiConnectError
            ? (error.originalError ?? error.message)
            : error instanceof Error
              ? error.message
              : String(error);
        const definitive = [
          "REVIEW_TICKET_EXPIRED",
          "REVIEW_PROFILE_CHANGED",
          "REVIEW_COLLECTION_CHANGED",
          "REVIEW_CARD_DELETED",
        ].some((code) => detail.startsWith(code));
        if (definitive) {
          await this.recoveryStore.clearSession(review_session_id);
        } else {
          await this.recoveryStore.markSession(
            review_session_id,
            "answer-uncertain",
          );
        }
      }
      this.logger.error(`Failed to rate card ${card_id}`, error);

      return createErrorResponse(error, {
        cardId: card_id,
        attemptedRating: rating,
        hint: "Make sure Anki is running and the card exists",
      });
    }
  }
}
