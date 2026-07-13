import { Test, TestingModule } from "@nestjs/testing";
import { RateCardTool } from "../rate-card.tool";
import { AnkiConnectClient } from "@/mcp/clients/anki-connect.client";
import { ChatReviewRecoveryStore } from "@/mcp/services/chat-review-recovery.store";
import {
  parseToolResult,
  createMockContext,
} from "@/test-fixtures/test-helpers";

jest.mock("@/mcp/clients/anki-connect.client");

describe("RateCardTool", () => {
  let tool: RateCardTool;
  let ankiClient: jest.Mocked<AnkiConnectClient>;
  let mockContext: ReturnType<typeof createMockContext>;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        RateCardTool,
        AnkiConnectClient,
        {
          provide: ChatReviewRecoveryStore,
          useValue: {
            clearSession: jest.fn(),
            markSession: jest.fn(),
          },
        },
      ],
    }).compile();

    tool = module.get<RateCardTool>(RateCardTool);
    ankiClient = module.get(
      AnkiConnectClient,
    ) as jest.Mocked<AnkiConnectClient>;
    mockContext = createMockContext();
    jest.clearAllMocks();
    ankiClient.getChatReviewCapabilities.mockResolvedValue(null);
  });

  it("should rate a valid card without fetching post-rating scheduling", async () => {
    const params = { card_id: 1502298033754, rating: 3 };

    ankiClient.invoke
      // 1) cardsInfo (validation)
      .mockResolvedValueOnce([{ cardId: params.card_id }])
      // 2) answerCards
      .mockResolvedValueOnce(true);

    const rawResult = await tool.rateCard(params, mockContext);
    const result = parseToolResult(rawResult);

    expect(ankiClient.invoke).toHaveBeenNthCalledWith(1, "cardsInfo", {
      cards: [params.card_id],
    });
    expect(ankiClient.invoke).toHaveBeenNthCalledWith(2, "answerCards", {
      answers: [{ cardId: params.card_id, ease: 3 }],
    });
    expect(ankiClient.invoke).toHaveBeenCalledTimes(2);
    expect(result.success).toBe(true);
    expect(result.cardId).toBe(params.card_id);
    expect(result.rating).toBe(3);
    expect(result.nextReview).toBeNull();
    expect(result.replayed).toBe(false);
  });

  it("uses a ticket when opaque review state is provided", async () => {
    ankiClient.getChatReviewCapabilities.mockResolvedValue({
      protocol: "chat-review/v1",
      supportsTickets: true,
      supportsIdempotentReplay: true,
      ticketProtocolVersion: "chat-review/v1",
      ankiVersion: "25.09.2",
      ankiVersionVerified: true,
      testedAnkiVersions: ["25.09.2"],
      fsrs: { enabled: true, scheduler: "fsrs" },
    });
    ankiClient.invoke.mockResolvedValue({
      success: true,
      replayed: false,
      ratedCard: {
        cardId: 111,
        rating: 3,
        ratingDescription: "Good",
      },
      next: null,
    });

    const result = parseToolResult(
      await tool.rateCard(
        {
          card_id: 111,
          rating: 3,
          review_session_id: "session",
          review_ticket: "ticket",
        },
        mockContext,
      ),
    );

    expect(result.success).toBe(true);
    expect(ankiClient.invoke).toHaveBeenCalledWith("chatReviewAnswer", {
      sessionId: "session",
      ticket: "ticket",
      cardId: 111,
      rating: 3,
      returnNext: false,
    });
    expect(ankiClient.invoke).toHaveBeenCalledTimes(1);
  });

  it("fails closed instead of calling answerCards on an unverified ticketed review", async () => {
    ankiClient.getChatReviewCapabilities.mockResolvedValue({
      protocol: "chat-review/v1",
      ticketProtocolVersion: "chat-review/v1",
      supportsTickets: true,
      supportsIdempotentReplay: true,
      ankiVersion: "99.1",
      ankiVersionVerified: false,
      testedAnkiVersions: ["25.09.2"],
      fsrs: { enabled: true, scheduler: "fsrs" },
    });

    const result = parseToolResult(
      await tool.rateCard(
        {
          card_id: 111,
          rating: 3,
          review_session_id: "session",
          review_ticket: "ticket",
        },
        mockContext,
      ),
    );

    expect(result.success).toBe(false);
    expect(result.error).toContain("ANKI_VERSION_UNVERIFIED");
    expect(ankiClient.invoke).not.toHaveBeenCalled();
  });

  it("should fail when card ID does not exist", async () => {
    const params = { card_id: 9999999999, rating: 3 };

    // cardsInfo returns an empty object for missing cards
    ankiClient.invoke.mockResolvedValueOnce([{}]);

    const rawResult = await tool.rateCard(params, mockContext);
    const result = parseToolResult(rawResult);

    // Only the validation call should fire; answerCards must NOT be invoked
    expect(ankiClient.invoke).toHaveBeenCalledTimes(1);
    expect(ankiClient.invoke).toHaveBeenCalledWith("cardsInfo", {
      cards: [params.card_id],
    });
    expect(result.success).toBe(false);
    expect(result.error).toContain("9999999999");
    expect(result.error).toContain("does not exist");
    expect(result.hint).toBeDefined();
  });

  it("should reject an invalid rating without hitting AnkiConnect", async () => {
    const rawResult = await tool.rateCard(
      { card_id: 1, rating: 7 },
      mockContext,
    );
    const result = parseToolResult(rawResult);

    expect(ankiClient.invoke).not.toHaveBeenCalled();
    expect(result.success).toBe(false);
    expect(result.error).toContain("Invalid rating");
  });

  it("should surface answerCards failure", async () => {
    const params = { card_id: 111, rating: 2 };

    ankiClient.invoke
      .mockResolvedValueOnce([{ cardId: 111 }]) // validation passes
      .mockResolvedValueOnce(false); // answerCards returns false

    const rawResult = await tool.rateCard(params, mockContext);
    const result = parseToolResult(rawResult);

    expect(result.success).toBe(false);
    expect(result.error).toContain("Failed to rate card 111");
  });
});
