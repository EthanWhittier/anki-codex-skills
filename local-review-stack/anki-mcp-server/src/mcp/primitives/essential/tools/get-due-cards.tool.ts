import { Injectable, Logger } from "@nestjs/common";
import { Tool } from "@rekog/mcp-nest";
import type { Context } from "@rekog/mcp-nest";
import { z } from "zod";
import { AnkiConnectClient } from "@/mcp/clients/anki-connect.client";
import {
  AnkiCard,
  AnkiDeckStatsResponse,
  CardType,
  SimplifiedCard,
} from "@/mcp/types/anki.types";
import {
  extractCardContent,
  createErrorResponse,
} from "@/mcp/utils/anki.utils";

/**
 * Tool for retrieving cards that are due for review
 */
@Injectable()
export class GetDueCardsTool {
  private readonly logger = new Logger(GetDueCardsTool.name);
  private readonly learnAheadSeconds = 20 * 60;

  constructor(private readonly ankiClient: AnkiConnectClient) {}

  private escapeDeckName(deckName: string): string {
    return deckName.replace(/"/g, '\\"');
  }

  private buildDeckScopedQuery(deckName: string | undefined, query: string) {
    if (!deckName) {
      return query;
    }

    return `"deck:${this.escapeDeckName(deckName)}" ${query}`;
  }

  private deckIncludesCard(
    requestedDeckName: string,
    cardDeckName: string | undefined,
  ) {
    return (
      cardDeckName === requestedDeckName ||
      cardDeckName?.startsWith(`${requestedDeckName}::`) === true
    );
  }

  private async getVisibleDeckCounts(deckName: string) {
    try {
      const statsByDeck = await this.ankiClient.invoke<
        Record<string, AnkiDeckStatsResponse>
      >("getDeckStats", {
        decks: [deckName],
      });
      const stats = Object.values(statsByDeck)[0];

      if (!stats) {
        return undefined;
      }

      return {
        new: stats.new_count || 0,
        learning: stats.learn_count || 0,
        review: stats.review_count || 0,
      };
    } catch (err) {
      // Non-fatal: if the scheduler counts are unavailable, preserve the older
      // direct-search behavior instead of failing the study session.
      this.logger.warn(
        `Could not read visible deck counts: ${err instanceof Error ? err.message : String(err)}`,
      );
      return undefined;
    }
  }

  private isLearningLike(card: AnkiCard) {
    return (
      card.type === CardType.Learning ||
      card.type === CardType.Relearning ||
      card.queue === 1 ||
      card.queue === 3
    );
  }

  private isUntouchedNew(card: AnkiCard, newCardIds: Set<number>) {
    return (
      newCardIds.has(card.cardId) &&
      card.type === CardType.New &&
      (card.reps ?? 0) === 0
    );
  }

  private isReviewLike(card: AnkiCard, dueCardIds: Set<number>) {
    if (!dueCardIds.has(card.cardId) || this.isLearningLike(card)) {
      return false;
    }

    return true;
  }

  private sortLearningCards(cards: AnkiCard[]) {
    return [...cards].sort((a, b) => {
      const attemptedDiff =
        Number((a.reps ?? 0) === 0) - Number((b.reps ?? 0) === 0);
      if (attemptedDiff !== 0) {
        return attemptedDiff;
      }

      return this.sortByDueThenId(a, b);
    });
  }

  private sortByDueThenId(a: AnkiCard, b: AnkiCard) {
    const dueDiff =
      (a.due ?? Number.MAX_SAFE_INTEGER) - (b.due ?? Number.MAX_SAFE_INTEGER);
    if (dueDiff !== 0) {
      return dueDiff;
    }

    return a.cardId - b.cardId;
  }

  private sortNewCards(cards: AnkiCard[]) {
    return [...cards].sort((a, b) => {
      const deckDiff = a.deckName.localeCompare(b.deckName, undefined, {
        sensitivity: "base",
      });
      if (deckDiff !== 0) {
        return deckDiff;
      }

      const dueDiff =
        (a.due ?? Number.MAX_SAFE_INTEGER) - (b.due ?? Number.MAX_SAFE_INTEGER);
      if (dueDiff !== 0) {
        return dueDiff;
      }

      const templateDiff = a.ord - b.ord;
      if (templateDiff !== 0) {
        return templateDiff;
      }

      return a.cardId - b.cardId;
    });
  }

  private orderCardsByStudyQueue(
    cards: AnkiCard[],
    dueCardIds: Set<number>,
    newCardIds: Set<number>,
  ): AnkiCard[] {
    const nowSeconds = Math.floor(Date.now() / 1000);
    const learnAheadCutoff = nowSeconds + this.learnAheadSeconds;

    const dueLearning: AnkiCard[] = [];
    const learnAhead: AnkiCard[] = [];
    const review: AnkiCard[] = [];
    const freshNew: AnkiCard[] = [];

    for (const card of cards) {
      if (this.isLearningLike(card)) {
        const due = card.due ?? Number.MAX_SAFE_INTEGER;
        if (due <= nowSeconds) {
          dueLearning.push(card);
        } else if (due <= learnAheadCutoff) {
          learnAhead.push(card);
        }
      } else if (this.isUntouchedNew(card, newCardIds)) {
        freshNew.push(card);
      } else if (this.isReviewLike(card, dueCardIds)) {
        review.push(card);
      }
    }

    const orderedDueLearning = this.sortLearningCards(dueLearning);
    const orderedReview = [...review].sort((a, b) =>
      this.sortByDueThenId(a, b),
    );
    const orderedNew = this.sortNewCards(freshNew);
    const orderedLearnAhead = this.sortLearningCards(learnAhead);

    if (orderedDueLearning.length > 0) {
      return [
        ...orderedDueLearning,
        ...this.orderMainQueue(orderedReview, orderedNew),
        ...orderedLearnAhead,
      ];
    }

    const orderedMainQueue = this.orderMainQueue(orderedReview, orderedNew);
    if (orderedMainQueue.length > 0) {
      return [...orderedMainQueue, ...orderedLearnAhead];
    }

    return orderedLearnAhead;
  }

  private orderMainQueue(review: AnkiCard[], freshNew: AnkiCard[]) {
    if (review.length === 0) {
      return freshNew;
    }

    if (freshNew.length > 0 && review.length < freshNew.length) {
      return [...freshNew, ...review];
    }

    return [...review, ...freshNew];
  }

  private simplifyCard(card: AnkiCard): SimplifiedCard {
    const { front, back } = extractCardContent(card.fields);

    return {
      cardId: card.cardId,
      front: front || card.question || "",
      back: back || card.answer || "",
      deckName: card.deckName,
      modelName: card.modelName,
      due: card.due || 0,
      interval: card.interval || 0,
      factor: card.factor || 2500,
    };
  }

  private cardIsAllowedByRequest(
    card: AnkiCard,
    includeLearning: boolean,
    includeNew: boolean,
  ) {
    if (!includeLearning && this.isLearningLike(card)) {
      return false;
    }

    if (!includeNew && card.type === CardType.New && (card.reps ?? 0) === 0) {
      return false;
    }

    return true;
  }

  private async getAnswerableGuiCard(
    deckName: string | undefined,
    includeLearning: boolean,
    includeNew: boolean,
    startedAt: number,
  ) {
    try {
      if (deckName) {
        const guiDeckReviewStartedAt = Date.now();
        const opened = await this.ankiClient.invoke<boolean>("guiDeckReview", {
          name: deckName,
        });
        this.logger.log(
          `[timing] getNextDueCardData guiDeckReview ${Date.now() - guiDeckReviewStartedAt}ms total=${Date.now() - startedAt}ms opened=${opened}`,
        );
        if (!opened) {
          return undefined;
        }
      }

      const currentStartedAt = Date.now();
      const currentCard = await this.ankiClient.invoke<{
        cardId?: number;
        deckName?: string;
      } | null>("guiCurrentCard");
      this.logger.log(
        `[timing] getNextDueCardData guiCurrentCard ${Date.now() - currentStartedAt}ms total=${Date.now() - startedAt}ms card=${currentCard?.cardId ?? "none"}`,
      );

      if (!currentCard?.cardId) {
        return undefined;
      }

      if (deckName && !this.deckIncludesCard(deckName, currentCard.deckName)) {
        this.logger.warn(
          `Ignoring GUI current card ${currentCard.cardId} from deck "${currentCard.deckName}" while requesting "${deckName}"`,
        );
        return undefined;
      }

      const cardsInfoStartedAt = Date.now();
      const cardsInfo = await this.ankiClient.invoke<AnkiCard[]>("cardsInfo", {
        cards: [currentCard.cardId],
      });
      this.logger.log(
        `[timing] getNextDueCardData guiCurrentCardsInfo ${Date.now() - cardsInfoStartedAt}ms total=${Date.now() - startedAt}ms count=${cardsInfo.length}`,
      );
      const card = cardsInfo[0];
      if (
        !card ||
        !this.cardIsAllowedByRequest(card, includeLearning, includeNew)
      ) {
        return undefined;
      }

      return this.simplifyCard(card);
    } catch (err) {
      this.logger.warn(
        `Could not read answerable GUI card: ${err instanceof Error ? err.message : String(err)}`,
      );
      return undefined;
    }
  }

  private async getCandidateIds(
    deckName: string | undefined,
    includeLearning: boolean,
    includeNew: boolean,
    visibleCounts?: { new: number; learning: number; review: number },
  ) {
    const dueStates: string[] = ["is:due"];
    if (includeLearning) {
      dueStates.push("is:learn");
    }

    const dueQuery = this.buildDeckScopedQuery(
      deckName,
      `-is:suspended (${dueStates.join(" OR ")})`,
    );
    const dueCardIds = await this.ankiClient.invoke<number[]>("findCards", {
      query: dueQuery,
    });

    let newCardIds: number[] = [];
    const visibleNewLimit = visibleCounts?.new;
    if (includeNew && (visibleNewLimit === undefined || visibleNewLimit > 0)) {
      const newQuery = this.buildDeckScopedQuery(
        deckName,
        "-is:suspended (is:new)",
      );
      const allNewCardIds = await this.ankiClient.invoke<number[]>(
        "findCards",
        {
          query: newQuery,
        },
      );
      newCardIds = allNewCardIds.slice(
        0,
        visibleNewLimit ?? allNewCardIds.length,
      );
    }

    return { dueCardIds, newCardIds };
  }

  private async getVisibleCountsForRequest(
    deckName: string | undefined,
    includeNew: boolean,
  ) {
    return deckName && includeNew
      ? await this.getVisibleDeckCounts(deckName)
      : undefined;
  }

  private visibleCountsAreEmpty(visibleCounts?: {
    new: number;
    learning: number;
    review: number;
  }) {
    return (
      visibleCounts &&
      visibleCounts.new === 0 &&
      visibleCounts.learning === 0 &&
      visibleCounts.review === 0
    );
  }

  async getNextDueCardData({
    deck_name,
    include_learning = true,
    include_new = false,
  }: {
    deck_name?: string;
    include_learning?: boolean;
    include_new?: boolean;
  }) {
    const startedAt = Date.now();
    this.logger.log(
      `[timing] getNextDueCardData start deck=${deck_name || "all"} include_learning=${include_learning} include_new=${include_new}`,
    );
    const visibleCountsStartedAt = Date.now();
    const visibleCounts = await this.getVisibleCountsForRequest(
      deck_name,
      include_new,
    );
    this.logger.log(
      `[timing] getNextDueCardData visibleCounts ${Date.now() - visibleCountsStartedAt}ms total=${Date.now() - startedAt}ms result=${visibleCounts ? JSON.stringify(visibleCounts) : "not_requested"}`,
    );
    if (this.visibleCountsAreEmpty(visibleCounts)) {
      this.logger.log(
        `[timing] getNextDueCardData done empty_visible_counts total=${Date.now() - startedAt}ms`,
      );
      return {
        success: true,
        card: null,
        total: 0,
        message: "No cards are due for review",
      };
    }

    const answerableCard = await this.getAnswerableGuiCard(
      deck_name,
      include_learning,
      include_new,
      startedAt,
    );
    if (answerableCard) {
      const total =
        visibleCounts !== undefined
          ? visibleCounts.learning + visibleCounts.review + visibleCounts.new
          : 1;
      this.logger.log(
        `[timing] getNextDueCardData done gui_current total=${Date.now() - startedAt}ms card=${answerableCard.cardId}`,
      );
      return {
        success: true,
        card: answerableCard,
        total,
        message: "Found next due card",
      };
    }

    const candidateIdsStartedAt = Date.now();
    const { dueCardIds, newCardIds } = await this.getCandidateIds(
      deck_name,
      include_learning,
      include_new,
      visibleCounts,
    );
    this.logger.log(
      `[timing] getNextDueCardData candidateIds ${Date.now() - candidateIdsStartedAt}ms total=${Date.now() - startedAt}ms due=${dueCardIds.length} new=${newCardIds.length}`,
    );
    const total = dueCardIds.length + newCardIds.length;

    if (total === 0) {
      this.logger.log(
        `[timing] getNextDueCardData done empty_candidates total=${Date.now() - startedAt}ms`,
      );
      return {
        success: true,
        card: null,
        total: 0,
        message: "No cards are due for review",
      };
    }

    let dueLearning: AnkiCard[] = [];
    let review: AnkiCard[] = [];
    let learnAhead: AnkiCard[] = [];

    if (dueCardIds.length > 0) {
      const dueCardsInfoStartedAt = Date.now();
      const dueCardsInfo = await this.ankiClient.invoke<AnkiCard[]>(
        "cardsInfo",
        {
          cards: dueCardIds,
        },
      );
      this.logger.log(
        `[timing] getNextDueCardData dueCardsInfo ${Date.now() - dueCardsInfoStartedAt}ms total=${Date.now() - startedAt}ms count=${dueCardsInfo.length}`,
      );
      const orderDueStartedAt = Date.now();
      const orderedDueCards = this.orderCardsByStudyQueue(
        dueCardsInfo,
        new Set(dueCardIds),
        new Set(),
      );
      const nowSeconds = Math.floor(Date.now() / 1000);
      const learnAheadCutoff = nowSeconds + this.learnAheadSeconds;
      dueLearning = orderedDueCards.filter(
        (card) => this.isLearningLike(card) && (card.due ?? 0) <= nowSeconds,
      );
      review = orderedDueCards.filter((card) =>
        this.isReviewLike(card, new Set(dueCardIds)),
      );
      learnAhead = orderedDueCards.filter((card) => {
        const due = card.due ?? Number.MAX_SAFE_INTEGER;
        return (
          this.isLearningLike(card) &&
          due > nowSeconds &&
          due <= learnAheadCutoff
        );
      });
      this.logger.log(
        `[timing] getNextDueCardData orderDueCards ${Date.now() - orderDueStartedAt}ms total=${Date.now() - startedAt}ms dueLearning=${dueLearning.length} review=${review.length} learnAhead=${learnAhead.length}`,
      );
    }

    const firstDueLearning = this.sortLearningCards(dueLearning)[0];
    if (firstDueLearning) {
      this.logger.log(
        `[timing] getNextDueCardData done first_due_learning total=${Date.now() - startedAt}ms card=${firstDueLearning.cardId}`,
      );
      return {
        success: true,
        card: this.simplifyCard(firstDueLearning),
        total,
        message: "Found next due card",
      };
    }

    const chooseNew =
      review.length === 0 ||
      (newCardIds.length > 0 && review.length < newCardIds.length);

    if (!chooseNew && review.length > 0) {
      const sortReviewStartedAt = Date.now();
      const firstReview = [...review].sort((a, b) =>
        this.sortByDueThenId(a, b),
      )[0];
      this.logger.log(
        `[timing] getNextDueCardData sortReview ${Date.now() - sortReviewStartedAt}ms total=${Date.now() - startedAt}ms card=${firstReview.cardId}`,
      );
      this.logger.log(
        `[timing] getNextDueCardData done first_review total=${Date.now() - startedAt}ms card=${firstReview.cardId}`,
      );
      return {
        success: true,
        card: this.simplifyCard(firstReview),
        total,
        message: "Found next due card",
      };
    }

    if (chooseNew && newCardIds.length > 0) {
      const newCardsInfoStartedAt = Date.now();
      const newCardsInfo = await this.ankiClient.invoke<AnkiCard[]>(
        "cardsInfo",
        {
          cards: newCardIds,
        },
      );
      this.logger.log(
        `[timing] getNextDueCardData newCardsInfo ${Date.now() - newCardsInfoStartedAt}ms total=${Date.now() - startedAt}ms count=${newCardsInfo.length}`,
      );
      const sortNewStartedAt = Date.now();
      const firstNew = this.sortNewCards(newCardsInfo)[0];
      this.logger.log(
        `[timing] getNextDueCardData sortNew ${Date.now() - sortNewStartedAt}ms total=${Date.now() - startedAt}ms card=${firstNew?.cardId ?? "none"}`,
      );
      if (firstNew) {
        this.logger.log(
          `[timing] getNextDueCardData done first_new total=${Date.now() - startedAt}ms card=${firstNew.cardId}`,
        );
        return {
          success: true,
          card: this.simplifyCard(firstNew),
          total,
          message: "Found next due card",
        };
      }
    }

    const sortLearnAheadStartedAt = Date.now();
    const firstLearnAhead = this.sortLearningCards(learnAhead)[0];
    this.logger.log(
      `[timing] getNextDueCardData sortLearnAhead ${Date.now() - sortLearnAheadStartedAt}ms total=${Date.now() - startedAt}ms card=${firstLearnAhead?.cardId ?? "none"}`,
    );
    this.logger.log(
      `[timing] getNextDueCardData done final total=${Date.now() - startedAt}ms card=${firstLearnAhead?.cardId ?? "none"}`,
    );
    return {
      success: true,
      card: firstLearnAhead ? this.simplifyCard(firstLearnAhead) : null,
      total,
      message: firstLearnAhead
        ? "Found next due card"
        : "No cards are due for review",
    };
  }

  @Tool({
    name: "get_due_cards",
    description:
      "Retrieve cards that are due for review from Anki. IMPORTANT: Use sync tool FIRST before getting cards to ensure latest data. After getting cards, use present_card to show them one by one to the user",
    parameters: z.object({
      deck_name: z
        .string()
        .optional()
        .describe(
          "Specific deck name to get cards from. If not specified, gets cards from all decks",
        ),
      limit: z
        .number()
        .min(1)
        .max(50)
        .default(10)
        .describe("Maximum number of cards to return"),
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
    }),
    outputSchema: z.object({
      success: z.boolean(),
      cards: z.array(
        z.object({
          cardId: z.number(),
          front: z.string(),
          back: z.string(),
          deckName: z.string(),
          modelName: z.string(),
          due: z.number(),
          interval: z.number(),
          factor: z.number(),
        }),
      ),
      total: z.number(),
      returned: z.number().optional(),
      message: z.string(),
    }),
    annotations: {
      title: "Get Due Cards",
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
    },
  })
  async getDueCards(
    {
      deck_name,
      limit,
      include_learning = true,
      include_new = false,
    }: {
      deck_name?: string;
      limit?: number;
      include_learning?: boolean;
      include_new?: boolean;
    },
    context: Context,
  ) {
    try {
      const cardLimit = Math.min(limit || 10, 50);

      this.logger.log(
        `Getting due cards from deck: ${deck_name || "all"}, limit: ${cardLimit}`,
      );
      await context.reportProgress({ progress: 10, total: 100 });

      const visibleCounts = await this.getVisibleCountsForRequest(
        deck_name,
        include_new,
      );
      if (this.visibleCountsAreEmpty(visibleCounts)) {
        this.logger.log("Visible scheduler counts are empty");
        await context.reportProgress({ progress: 100, total: 100 });
        return {
          success: true,
          message: "No cards are due for review",
          cards: [],
          total: 0,
        };
      }

      const { dueCardIds, newCardIds } = await this.getCandidateIds(
        deck_name,
        include_learning,
        include_new,
        visibleCounts,
      );

      const cardIds = [...dueCardIds, ...newCardIds];

      if (cardIds.length === 0) {
        this.logger.log("No due cards found");
        await context.reportProgress({ progress: 100, total: 100 });
        return {
          success: true,
          message: "No cards are due for review",
          cards: [],
          total: 0,
        };
      }

      await context.reportProgress({ progress: 50, total: 100 });

      const newCount = newCardIds.length;
      const dueOnlyCount = dueCardIds.length;

      // Fetch scheduler metadata before limiting so the deterministic queue can
      // choose between due learning, review, available new, and learn-ahead.
      const cardsInfo = await this.ankiClient.invoke<AnkiCard[]>("cardsInfo", {
        cards: cardIds,
      });
      const selectedCardsInfo = this.orderCardsByStudyQueue(
        cardsInfo,
        new Set(dueCardIds),
        new Set(newCardIds),
      ).slice(0, cardLimit);

      // Transform cards to simplified structure
      const dueCards: SimplifiedCard[] = selectedCardsInfo.map((card) =>
        this.simplifyCard(card),
      );

      await context.reportProgress({ progress: 100, total: 100 });
      this.logger.log(
        `Retrieved ${dueCards.length} cards out of ${cardIds.length} total`,
      );

      const message = include_new
        ? `Found ${cardIds.length} cards (${newCount} new, ${dueOnlyCount} due), returning ${dueCards.length}`
        : `Found ${cardIds.length} due cards, returning ${dueCards.length}`;

      return {
        success: true,
        cards: dueCards,
        total: cardIds.length,
        returned: dueCards.length,
        message,
      };
    } catch (error) {
      this.logger.error("Failed to get due cards", error);
      return createErrorResponse(error);
    }
  }
}
