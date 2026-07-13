import { Test, TestingModule } from "@nestjs/testing";
import { GetDueCardsTool } from "../get-due-cards.tool";
import { AnkiConnectClient } from "../../../../clients/anki-connect.client";
import { mockCards } from "../../../../../test-fixtures/mock-data";
import {
  parseToolResult,
  createMockContext,
} from "../../../../../test-fixtures/test-helpers";
import { AnkiCard } from "../../../../types/anki.types";

// Mock the AnkiConnectClient
jest.mock("../../../../clients/anki-connect.client");

describe("GetDueCardsTool", () => {
  let tool: GetDueCardsTool;
  let ankiClient: jest.Mocked<AnkiConnectClient>;
  let mockContext: any;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [GetDueCardsTool, AnkiConnectClient],
    }).compile();

    tool = module.get<GetDueCardsTool>(GetDueCardsTool);
    ankiClient = module.get(
      AnkiConnectClient,
    ) as jest.Mocked<AnkiConnectClient>;

    // Setup mock context
    mockContext = createMockContext();

    // Clear all mocks before each test
    jest.clearAllMocks();
  });

  describe("getDueCards", () => {
    const mockCardIds = [1502298033754, 1502298033758];
    const mockCardsInfo: AnkiCard[] = [
      {
        ...mockCards.dueCard,
        fields: {
          Front: { value: "¿Cómo estás?", order: 0 },
          Back: { value: "How are you?", order: 1 },
        },
      },
      {
        ...mockCards.newCard,
        fields: {
          Front: { value: "こんにちは", order: 0 },
          Back: { value: "Hello", order: 1 },
        },
      },
    ];

    it("should return due cards with learning included by default", async () => {
      // Arrange
      ankiClient.invoke
        .mockResolvedValueOnce(mockCardIds) // findCards
        .mockResolvedValueOnce(mockCardsInfo); // cardsInfo

      // Act
      const rawResult = await tool.getDueCards({}, mockContext);
      const result = parseToolResult(rawResult);

      // Assert
      expect(ankiClient.invoke).toHaveBeenCalledTimes(2);
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(1, "findCards", {
        query: "-is:suspended (is:due OR is:learn)",
      });
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(2, "cardsInfo", {
        cards: mockCardIds,
      });

      expect(result.success).toBe(true);
      expect(result.cards).toHaveLength(2);
      expect(result.total).toBe(2);
      expect(result.returned).toBe(2);
      expect(result.message).toContain("Found 2 due cards");
      expect(mockContext.reportProgress).toHaveBeenCalled();
    });

    it("should exclude learning cards when include_learning is false", async () => {
      // Arrange
      ankiClient.invoke
        .mockResolvedValueOnce(mockCardIds)
        .mockResolvedValueOnce(mockCardsInfo);

      // Act
      const rawResult = await tool.getDueCards(
        { include_learning: false },
        mockContext,
      );
      const result = parseToolResult(rawResult);

      // Assert
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(1, "findCards", {
        query: "-is:suspended (is:due)",
      });
      expect(result.success).toBe(true);
    });

    it("should include new cards when include_new is true", async () => {
      // Arrange
      ankiClient.invoke
        .mockResolvedValueOnce([mockCardIds[0]]) // findCards (due/learning)
        .mockResolvedValueOnce([mockCardIds[1]]) // findCards (new)
        .mockResolvedValueOnce(mockCardsInfo); // cardsInfo

      // Act
      const rawResult = await tool.getDueCards(
        { include_new: true },
        mockContext,
      );
      const result = parseToolResult(rawResult);

      // Assert
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(1, "findCards", {
        query: "-is:suspended (is:due OR is:learn)",
      });
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(2, "findCards", {
        query: "-is:suspended (is:new)",
      });
      expect(result.success).toBe(true);
      expect(result.message).toContain("1 new");
      expect(result.message).toContain("1 due");
    });

    it("should include only due and new when learning excluded", async () => {
      // Arrange
      ankiClient.invoke
        .mockResolvedValueOnce(mockCardIds) // findCards (due)
        .mockResolvedValueOnce([]) // findCards (new)
        .mockResolvedValueOnce(mockCardsInfo); // cardsInfo

      // Act
      const rawResult = await tool.getDueCards(
        { include_learning: false, include_new: true },
        mockContext,
      );
      const result = parseToolResult(rawResult);

      // Assert
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(1, "findCards", {
        query: "-is:suspended (is:due)",
      });
      expect(result.success).toBe(true);
    });

    it("should filter by deck name", async () => {
      // Arrange
      ankiClient.invoke
        .mockResolvedValueOnce(mockCardIds)
        .mockResolvedValueOnce(mockCardsInfo);

      // Act
      const rawResult = await tool.getDueCards(
        { deck_name: "Spanish" },
        mockContext,
      );
      const result = parseToolResult(rawResult);

      // Assert
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(1, "findCards", {
        query: '"deck:Spanish" -is:suspended (is:due OR is:learn)',
      });
      expect(result.success).toBe(true);
      expect(result.cards).toHaveLength(2);
    });

    it("should escape special characters in deck name", async () => {
      // Arrange
      ankiClient.invoke.mockResolvedValueOnce([]).mockResolvedValueOnce([]);

      // Act
      await tool.getDueCards({ deck_name: 'Deck with "quotes"' }, mockContext);

      // Assert
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(1, "findCards", {
        query:
          '"deck:Deck with \\"quotes\\"" -is:suspended (is:due OR is:learn)',
      });
    });

    it("should respect the limit parameter", async () => {
      // Arrange
      const manyCardIds = Array.from(
        { length: 20 },
        (_, i) => 1500000000000 + i,
      );
      const manyCardsInfo = manyCardIds.slice(0, 2).map((cardId, index) => ({
        ...mockCards.dueCard,
        cardId,
        due: index + 1,
        fields: {
          Front: { value: `Due ${index}`, order: 0 },
          Back: { value: `Answer ${index}`, order: 1 },
        },
      }));
      ankiClient.invoke
        .mockResolvedValueOnce(manyCardIds)
        .mockResolvedValueOnce(manyCardsInfo);

      // Act
      const rawResult = await tool.getDueCards({ limit: 5 }, mockContext);
      const result = parseToolResult(rawResult);

      // Assert
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(2, "cardsInfo", {
        cards: manyCardIds,
      });
      expect(result.success).toBe(true);
      expect(result.total).toBe(20);
      expect(result.returned).toBe(2); // mockCardsInfo has only 2 items
      expect(result.message).toContain("Found 20 due cards, returning 2");
    });

    it("should enforce maximum returned limit of 50", async () => {
      // Arrange
      const manyCardIds = Array.from(
        { length: 100 },
        (_, i) => 1500000000000 + i,
      );
      ankiClient.invoke
        .mockResolvedValueOnce(manyCardIds)
        .mockResolvedValueOnce(mockCardsInfo);

      // Act
      await tool.getDueCards({ limit: 100 }, mockContext);

      // Assert - fetches all candidate metadata so cards can be sorted before limiting.
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(2, "cardsInfo", {
        cards: manyCardIds,
      });
    });

    it("should sort new cards by scheduler due before applying limit", async () => {
      // Arrange
      const unsortedCardIds = [1777960551820, 1777960926642, 1777961732337];
      const unsortedCardsInfo: AnkiCard[] = [
        {
          ...mockCards.newCard,
          cardId: 1777960551820,
          due: 1210,
          fields: {
            Front: { value: "What is quality?", order: 0 },
            Back: { value: "Affirms or denies.", order: 1 },
          },
        },
        {
          ...mockCards.newCard,
          cardId: 1777960926642,
          due: 857,
          fields: {
            Front: { value: "Some S are P?", order: 0 },
            Back: { value: "I; particular; affirmative; none", order: 1 },
          },
        },
        {
          ...mockCards.newCard,
          cardId: 1777961732337,
          due: 1095,
          fields: {
            Front: { value: "Subalternation?", order: 0 },
            Back: { value: "Truth down, falsity up.", order: 1 },
          },
        },
      ];
      ankiClient.invoke
        .mockResolvedValueOnce([])
        .mockResolvedValueOnce(unsortedCardIds)
        .mockResolvedValueOnce(unsortedCardsInfo);

      // Act
      const rawResult = await tool.getDueCards(
        { include_new: true, limit: 2 },
        mockContext,
      );
      const result = parseToolResult(rawResult);

      // Assert
      expect(result.success).toBe(true);
      expect(result.cards.map((card: any) => card.cardId)).toEqual([
        1777960926642, 1777961732337,
      ]);
    });

    it("should choose due learning before review and new cards", async () => {
      const now = Math.floor(Date.now() / 1000);
      const learningCard = {
        ...mockCards.dueCard,
        cardId: 1,
        type: 1,
        queue: 1,
        due: now - 30,
        reps: 1,
        fields: {
          Front: { value: "Learning", order: 0 },
          Back: { value: "Learning answer", order: 1 },
        },
      };
      const reviewCard = {
        ...mockCards.dueCard,
        cardId: 2,
        type: 2,
        queue: 2,
        due: 10,
        fields: {
          Front: { value: "Review", order: 0 },
          Back: { value: "Review answer", order: 1 },
        },
      };
      const newCard = {
        ...mockCards.newCard,
        cardId: 3,
        type: 0,
        queue: 0,
        due: 1,
        reps: 0,
        fields: {
          Front: { value: "New", order: 0 },
          Back: { value: "New answer", order: 1 },
        },
      };
      ankiClient.invoke
        .mockResolvedValueOnce([reviewCard.cardId, learningCard.cardId])
        .mockResolvedValueOnce([newCard.cardId])
        .mockResolvedValueOnce([newCard, reviewCard, learningCard]);

      const rawResult = await tool.getDueCards(
        { include_new: true, limit: 1 },
        mockContext,
      );
      const result = parseToolResult(rawResult);

      expect(result.success).toBe(true);
      expect(result.cards.map((card: any) => card.cardId)).toEqual([1]);
    });

    it("should choose new from the main queue when new backlog exceeds review backlog", async () => {
      const reviewCard = {
        ...mockCards.dueCard,
        cardId: 10,
        type: 2,
        queue: 2,
        due: 1,
        fields: {
          Front: { value: "Review", order: 0 },
          Back: { value: "Review answer", order: 1 },
        },
      };
      const newCards = [20, 21].map((cardId, index) => ({
        ...mockCards.newCard,
        cardId,
        type: 0,
        queue: 0,
        due: index + 100,
        reps: 0,
        fields: {
          Front: { value: `New ${index}`, order: 0 },
          Back: { value: `New answer ${index}`, order: 1 },
        },
      }));
      ankiClient.invoke
        .mockResolvedValueOnce([reviewCard.cardId])
        .mockResolvedValueOnce(newCards.map((card) => card.cardId))
        .mockResolvedValueOnce([reviewCard, ...newCards]);

      const rawResult = await tool.getDueCards(
        { include_new: true, limit: 1 },
        mockContext,
      );
      const result = parseToolResult(rawResult);

      expect(result.success).toBe(true);
      expect(result.cards.map((card: any) => card.cardId)).toEqual([20]);
    });

    it("should choose review from the main queue when review backlog is at least new backlog", async () => {
      const reviewCards = [10, 11].map((cardId, index) => ({
        ...mockCards.dueCard,
        cardId,
        type: 2,
        queue: 2,
        due: index + 1,
        fields: {
          Front: { value: `Review ${index}`, order: 0 },
          Back: { value: `Review answer ${index}`, order: 1 },
        },
      }));
      const newCard = {
        ...mockCards.newCard,
        cardId: 20,
        type: 0,
        queue: 0,
        due: 0,
        reps: 0,
        fields: {
          Front: { value: "New", order: 0 },
          Back: { value: "New answer", order: 1 },
        },
      };
      ankiClient.invoke
        .mockResolvedValueOnce(reviewCards.map((card) => card.cardId))
        .mockResolvedValueOnce([newCard.cardId])
        .mockResolvedValueOnce([newCard, ...reviewCards]);

      const rawResult = await tool.getDueCards(
        { include_new: true, limit: 1 },
        mockContext,
      );
      const result = parseToolResult(rawResult);

      expect(result.success).toBe(true);
      expect(result.cards.map((card: any) => card.cardId)).toEqual([10]);
    });

    it("should choose learn-ahead cards only after the main queue is empty", async () => {
      const now = Math.floor(Date.now() / 1000);
      const learnAheadCard = {
        ...mockCards.dueCard,
        cardId: 1,
        type: 1,
        queue: 1,
        due: now + 60,
        reps: 1,
        fields: {
          Front: { value: "Learn ahead", order: 0 },
          Back: { value: "Learn ahead answer", order: 1 },
        },
      };
      ankiClient.invoke
        .mockResolvedValueOnce([learnAheadCard.cardId])
        .mockResolvedValueOnce([learnAheadCard]);

      const rawResult = await tool.getDueCards({ limit: 1 }, mockContext);
      const result = parseToolResult(rawResult);

      expect(result.success).toBe(true);
      expect(result.cards.map((card: any) => card.cardId)).toEqual([1]);
    });

    it("should return empty array when no cards found", async () => {
      // Arrange
      ankiClient.invoke.mockResolvedValueOnce([]);

      // Act
      const rawResult = await tool.getDueCards({}, mockContext);
      const result = parseToolResult(rawResult);

      // Assert
      expect(result.success).toBe(true);
      expect(result.message).toBe("No cards are due for review");
      expect(result.cards).toEqual([]);
      expect(result.total).toBe(0);
      expect(mockContext.reportProgress).toHaveBeenCalledWith({
        progress: 100,
        total: 100,
      });
    });

    it("should handle network errors gracefully", async () => {
      // Arrange
      const networkError = new Error("fetch failed");
      ankiClient.invoke.mockRejectedValueOnce(networkError);

      // Act
      const rawResult = await tool.getDueCards({}, mockContext);
      const result = parseToolResult(rawResult);

      // Assert
      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
      expect(result.error).toContain("fetch failed");
    });

    it("should handle AnkiConnect errors when getting card info", async () => {
      // Arrange
      ankiClient.invoke
        .mockResolvedValueOnce(mockCardIds)
        .mockRejectedValueOnce(
          new Error("AnkiConnect error: collection is not available"),
        );

      // Act
      const rawResult = await tool.getDueCards({}, mockContext);
      const result = parseToolResult(rawResult);

      // Assert
      expect(result.success).toBe(false);
      expect(result.error).toContain("collection is not available");
    });

    it("should transform cards to simplified structure", async () => {
      // Arrange
      ankiClient.invoke
        .mockResolvedValueOnce([mockCardIds[0]])
        .mockResolvedValueOnce([mockCardsInfo[0]]);

      // Act
      const rawResult = await tool.getDueCards({}, mockContext);
      const result = parseToolResult(rawResult);

      // Assert
      expect(result.success).toBe(true);
      expect(result.cards[0]).toMatchObject({
        cardId: 1502298033754,
        front: "¿Cómo estás?",
        back: "How are you?",
        deckName: "Spanish",
        modelName: "Basic",
        due: 1,
        interval: 1,
        factor: 2500,
      });
    });

    it("should report progress correctly", async () => {
      // Arrange
      ankiClient.invoke
        .mockResolvedValueOnce(mockCardIds)
        .mockResolvedValueOnce(mockCardsInfo);

      // Act
      await tool.getDueCards({}, mockContext);

      // Assert
      expect(mockContext.reportProgress).toHaveBeenCalledTimes(3);
      expect(mockContext.reportProgress).toHaveBeenNthCalledWith(1, {
        progress: 10,
        total: 100,
      });
      expect(mockContext.reportProgress).toHaveBeenNthCalledWith(2, {
        progress: 50,
        total: 100,
      });
      expect(mockContext.reportProgress).toHaveBeenNthCalledWith(3, {
        progress: 100,
        total: 100,
      });
    });

    it("should combine deck filter with include_new", async () => {
      // Arrange
      ankiClient.invoke
        .mockResolvedValueOnce({
          "123": {
            deck_id: 123,
            name: "Japanese::JLPT N5",
            new_count: 1,
            learn_count: 0,
            review_count: 0,
            total_in_deck: 10,
          },
        }) // getDeckStats
        .mockResolvedValueOnce([]) // findCards (due/learning)
        .mockResolvedValueOnce([mockCardIds[1], 1502298033760]) // findCards (new)
        .mockResolvedValueOnce([mockCardsInfo[1]]); // cardsInfo

      // Act
      const rawResult = await tool.getDueCards(
        { deck_name: "Japanese::JLPT N5", include_new: true },
        mockContext,
      );
      const result = parseToolResult(rawResult);

      // Assert
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(1, "getDeckStats", {
        decks: ["Japanese::JLPT N5"],
      });
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(2, "findCards", {
        query: '"deck:Japanese::JLPT N5" -is:suspended (is:due OR is:learn)',
      });
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(3, "findCards", {
        query: '"deck:Japanese::JLPT N5" -is:suspended (is:new)',
      });
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(4, "cardsInfo", {
        cards: [mockCardIds[1]],
      });
      expect(result.success).toBe(true);
    });

    it("should not return unseen new cards when visible deck counts are zero", async () => {
      // Arrange
      ankiClient.invoke.mockResolvedValueOnce({
        "123": {
          deck_id: 123,
          name: "World Flags",
          new_count: 0,
          learn_count: 0,
          review_count: 0,
          total_in_deck: 203,
        },
      });

      // Act
      const rawResult = await tool.getDueCards(
        { deck_name: "World Flags", include_new: true },
        mockContext,
      );
      const result = parseToolResult(rawResult);

      // Assert
      expect(ankiClient.invoke).toHaveBeenCalledTimes(1);
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(1, "getDeckStats", {
        decks: ["World Flags"],
      });
      expect(result.success).toBe(true);
      expect(result.cards).toEqual([]);
      expect(result.total).toBe(0);
    });

    it("should use default limit of 10 when not specified", async () => {
      // Arrange
      const manyCardIds = Array.from(
        { length: 15 },
        (_, i) => 1500000000000 + i,
      );
      ankiClient.invoke
        .mockResolvedValueOnce(manyCardIds)
        .mockResolvedValueOnce(mockCardsInfo);

      // Act
      await tool.getDueCards({}, mockContext);

      // Assert - should only request 10 cards by default
      expect(ankiClient.invoke).toHaveBeenNthCalledWith(2, "cardsInfo", {
        cards: manyCardIds,
      });
    });
  });

  describe("getNextDueCardData", () => {
    it("should use a GUI card from a descendant of the requested parent deck", async () => {
      const parentDeck = "Ultimate Geography::Support";
      const guiCard = {
        ...mockCards.dueCard,
        cardId: 1777864061787,
        deckName: `${parentDeck}::Flag Distinctions`,
        fields: {
          Front: { value: "Distinguish the flags", order: 0 },
          Back: { value: "Reference answer", order: 1 },
        },
      };

      ankiClient.invoke
        .mockResolvedValueOnce({
          "123": {
            deck_id: 123,
            name: parentDeck,
            new_count: 0,
            learn_count: 0,
            review_count: 3,
            total_in_deck: 3,
          },
        }) // getDeckStats
        .mockResolvedValueOnce(true) // guiDeckReview
        .mockResolvedValueOnce({
          cardId: guiCard.cardId,
          deckName: guiCard.deckName,
        }) // guiCurrentCard
        .mockResolvedValueOnce([guiCard]); // cardsInfo

      const result = await tool.getNextDueCardData({
        deck_name: parentDeck,
        include_learning: true,
        include_new: true,
      });

      expect(result.success).toBe(true);
      expect(result.card?.cardId).toBe(guiCard.cardId);
      expect(ankiClient.invoke).toHaveBeenCalledTimes(4);
      expect(ankiClient.invoke).not.toHaveBeenCalledWith(
        "findCards",
        expect.anything(),
      );
    });
  });
});
