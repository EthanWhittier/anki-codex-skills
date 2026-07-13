import { Injectable, Logger } from "@nestjs/common";
import { Tool } from "@rekog/mcp-nest";
import type { Context } from "@rekog/mcp-nest";
import { z } from "zod";
import {
  AnkiConnectClient,
  AnkiConnectError,
} from "@/mcp/clients/anki-connect.client";
import type { ChatReviewAnswerResponse } from "@/mcp/types/anki.types";
import { GetDueCardsTool } from "./get-due-cards.tool";
import {
  createErrorResponse,
  getRatingDescription,
} from "@/mcp/utils/anki.utils";
import { compactRenderedReviewCard } from "@/mcp/utils/rendered-card-content.utils";
import { ChatReviewRecoveryStore } from "@/mcp/services/chat-review-recovery.store";

/**
 * Fast review-step tool: rate the current card and return the next card.
 */
@Injectable()
export class RateCardAndGetNextTool {
  private readonly logger = new Logger(RateCardAndGetNextTool.name);

  constructor(
    private readonly ankiClient: AnkiConnectClient,
    private readonly getDueCardsTool: GetDueCardsTool,
    private readonly recoveryStore: ChatReviewRecoveryStore,
  ) {}

  @Tool({
    name: "rate_card_and_get_next",
    description:
      "Fast review step: submit the user's rating for the current card, then retrieve the next available card using Anki's visible scheduler queue. Use during chat review after the user gives a rating.",
    parameters: z.object({
      card_id: z.number().describe("The ID of the current card to rate"),
      rating: z
        .number()
        .min(1)
        .max(4)
        .describe("The user's chosen rating: 1=Again, 2=Hard, 3=Good, 4=Easy"),
      deck_name: z
        .string()
        .optional()
        .describe(
          "Specific deck name to get the next card from. If not specified, gets the next card from all decks",
        ),
      include_learning: z
        .boolean()
        .default(true)
        .describe("Include learning/relearning cards. Default: true"),
      include_new: z.boolean().default(false).describe("Include new cards."),
      review_session_id: z
        .string()
        .optional()
        .describe(
          "Opaque active review session; never display to the learner.",
        ),
      review_ticket: z
        .string()
        .optional()
        .describe(
          "Opaque pending review ticket; never display to the learner.",
        ),
    }),
    outputSchema: z.object({
      success: z.boolean(),
      ratedCard: z.object({
        cardId: z.number(),
        rating: z.number(),
        ratingDescription: z.string(),
      }),
      nextCard: z
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
      replayed: z.boolean(),
    }),
    // This local deployment intentionally preserves the fast review metadata.
    // Scheduling still occurs, but the chat-review skill obtains an explicit
    // learner rating before calling this tool, avoiding per-card prompt latency.
    annotations: {
      title: "Rate Card and Get Next",
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
    },
  })
  async rateCardAndGetNext(
    {
      card_id,
      rating,
      deck_name,
      include_learning = true,
      include_new = false,
      review_session_id,
      review_ticket,
    }: {
      card_id: number;
      rating: number;
      deck_name?: string;
      include_learning?: boolean;
      include_new?: boolean;
      review_session_id?: string;
      review_ticket?: string;
    },
    context: Context,
  ) {
    const startedAt = Date.now();
    let ticketAnswerAttempted = false;
    try {
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

      this.logger.log(`Fast rating card ${card_id} with rating ${rating}`);
      this.logger.log(
        `[timing] rate_card_and_get_next start card=${card_id} rating=${rating} deck=${deck_name || "all"} include_learning=${include_learning} include_new=${include_new}`,
      );
      const progress20StartedAt = Date.now();
      await context.reportProgress({ progress: 20, total: 100 });
      this.logger.log(
        `[timing] rate_card_and_get_next progress20 ${Date.now() - progress20StartedAt}ms total=${Date.now() - startedAt}ms`,
      );

      const answerStartedAt = Date.now();
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
        const ticketed = await this.ankiClient.invoke<ChatReviewAnswerResponse>(
          "chatReviewAnswer",
          {
            sessionId: review_session_id,
            ticket: review_ticket,
            cardId: card_id,
            rating,
            returnNext: true,
          },
        );
        if (ticketed.ratedCard.cardId !== card_id) {
          throw new Error(
            `REVIEW_CARD_MISMATCH: Anki returned card ${ticketed.ratedCard.cardId} while rating ${card_id}`,
          );
        }
        const next = ticketed.next;
        if (
          capabilities.supportsRecovery &&
          typeof capabilities.generationHash === "string" &&
          next?.ticket &&
          next.card
        ) {
          await this.recoveryStore.save(
            {
              endpointHash: this.ankiClient.endpointIdentifierHash,
              generationHash: capabilities.generationHash,
              protocol: capabilities.protocol,
            },
            review_session_id,
            deck_name ?? next.card.deckName,
            next.card.cardId,
          );
        } else {
          await this.recoveryStore.clearSession(review_session_id);
        }
        await context.reportProgress({ progress: 100, total: 100 });
        return {
          success: ticketed.success,
          ratedCard: ticketed.ratedCard,
          nextCard: next?.card ? compactRenderedReviewCard(next.card) : null,
          total: next?.total ?? 0,
          message: next?.card
            ? "Card rated and next card found"
            : "Card rated; no cards are due for review",
          reviewSessionId: next?.ticket ? review_session_id : null,
          reviewTicket: next?.ticket ?? null,
          replayed: ticketed.replayed,
        };
      }

      const answered = await this.answerLegacyWithExactQueueRetry(
        card_id,
        rating,
      );
      this.logger.log(
        `[timing] rate_card_and_get_next answerCards ${Date.now() - answerStartedAt}ms total=${Date.now() - startedAt}ms`,
      );

      if (!answered) {
        throw new Error(`Failed to rate card ${card_id}`);
      }

      const progress55StartedAt = Date.now();
      await context.reportProgress({ progress: 55, total: 100 });
      this.logger.log(
        `[timing] rate_card_and_get_next progress55 ${Date.now() - progress55StartedAt}ms total=${Date.now() - startedAt}ms`,
      );

      const nextStartedAt = Date.now();
      const next = await this.getDueCardsTool.getNextDueCardData({
        deck_name,
        include_learning,
        include_new,
      });
      this.logger.log(
        `[timing] rate_card_and_get_next getNextDueCardData ${Date.now() - nextStartedAt}ms total=${Date.now() - startedAt}ms nextCard=${next.card?.cardId ?? "none"} totalCandidates=${next.total ?? "unknown"}`,
      );

      if (!next.success) {
        this.logger.log(
          `[timing] rate_card_and_get_next done error_result total=${Date.now() - startedAt}ms`,
        );
        return next;
      }

      const progress100StartedAt = Date.now();
      await context.reportProgress({ progress: 100, total: 100 });
      this.logger.log(
        `[timing] rate_card_and_get_next progress100 ${Date.now() - progress100StartedAt}ms total=${Date.now() - startedAt}ms`,
      );

      const ratingDescription = getRatingDescription(rating);
      this.logger.log(
        `[timing] rate_card_and_get_next done success total=${Date.now() - startedAt}ms`,
      );
      return {
        success: true,
        ratedCard: {
          cardId: card_id,
          rating,
          ratingDescription,
        },
        nextCard: next.card,
        total: next.total,
        message: next.card
          ? "Card rated and next card found"
          : "Card rated; no cards are due for review",
        reviewSessionId: null,
        reviewTicket: null,
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
      this.logger.error(`Failed fast review step for card ${card_id}`, error);
      this.logger.log(
        `[timing] rate_card_and_get_next done exception total=${Date.now() - startedAt}ms`,
      );
      return createErrorResponse(error, {
        cardId: card_id,
        attemptedRating: rating,
        hint: "Make sure Anki is running and the card exists",
      });
    }
  }

  private async answerLegacyWithExactQueueRetry(
    cardId: number,
    rating: number,
  ): Promise<boolean> {
    const answer = () =>
      this.ankiClient.invoke<boolean>("answerCards", {
        answers: [{ cardId, ease: rating }],
      });

    try {
      return await answer();
    } catch (error) {
      const isExactQueueRace =
        error instanceof AnkiConnectError &&
        error.originalError === "not at top of queue";
      if (!isExactQueueRace) {
        throw error;
      }

      const cards = await this.ankiClient.invoke<Array<{ cardId?: number }>>(
        "cardsInfo",
        { cards: [cardId] },
      );
      if (cards[0]?.cardId !== cardId) {
        throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, 75));
      return answer();
    }
  }
}
