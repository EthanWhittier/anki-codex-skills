import { Test, TestingModule } from "@nestjs/testing";
import { RateCardAndGetNextTool } from "../rate-card-and-get-next.tool";
import {
  AnkiConnectClient,
  AnkiConnectError,
} from "../../../../clients/anki-connect.client";
import { GetDueCardsTool } from "../get-due-cards.tool";
import { ChatReviewRecoveryStore } from "../../../../services/chat-review-recovery.store";
import {
  createMockContext,
  parseToolResult,
} from "../../../../../test-fixtures/test-helpers";

jest.mock("../../../../clients/anki-connect.client");

describe("RateCardAndGetNextTool", () => {
  let tool: RateCardAndGetNextTool;
  let ankiClient: jest.Mocked<AnkiConnectClient>;
  let getDueCardsTool: jest.Mocked<GetDueCardsTool>;
  let mockContext: any;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        RateCardAndGetNextTool,
        AnkiConnectClient,
        {
          provide: ChatReviewRecoveryStore,
          useValue: {
            save: jest.fn(),
            clearSession: jest.fn(),
            markSession: jest.fn(),
          },
        },
        {
          provide: GetDueCardsTool,
          useValue: {
            getNextDueCardData: jest.fn(),
          },
        },
      ],
    }).compile();

    tool = module.get<RateCardAndGetNextTool>(RateCardAndGetNextTool);
    ankiClient = module.get(
      AnkiConnectClient,
    ) as jest.Mocked<AnkiConnectClient>;
    getDueCardsTool = module.get(
      GetDueCardsTool,
    ) as jest.Mocked<GetDueCardsTool>;
    mockContext = createMockContext();
    jest.clearAllMocks();
    ankiClient.getChatReviewCapabilities.mockResolvedValue(null);
  });

  it("answers a ticket exactly once and propagates the next ticket", async () => {
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
      replayed: true,
      ratedCard: {
        cardId: 123,
        rating: 3,
        ratingDescription: "Good",
      },
      next: {
        success: true,
        ticket: "next-ticket",
        card: {
          cardId: 456,
          front: "<style>.card { color: red; }</style><div>next</div>",
          back: "<style>.card { color: red; }</style><div>next</div><hr><div>answer</div>",
          deckName: "Logic",
          modelName: "Basic",
          due: 1,
          interval: 0,
          factor: 2500,
        },
        total: 1,
      },
    });

    const result = parseToolResult(
      await tool.rateCardAndGetNext(
        {
          card_id: 123,
          rating: 3,
          review_session_id: "session",
          review_ticket: "ticket",
        },
        mockContext,
      ),
    );

    expect(ankiClient.invoke).toHaveBeenCalledTimes(1);
    expect(ankiClient.invoke).toHaveBeenCalledWith("chatReviewAnswer", {
      sessionId: "session",
      ticket: "ticket",
      cardId: 123,
      rating: 3,
      returnNext: true,
    });
    expect(result.replayed).toBe(true);
    expect(result.reviewTicket).toBe("next-ticket");
    expect(result.nextCard).toMatchObject({
      cardId: 456,
      front: "next",
      back: "answer",
    });
    expect(JSON.stringify(result.nextCard)).not.toContain("ticket");
    expect(getDueCardsTool.getNextDueCardData).not.toHaveBeenCalled();
  });

  it("preserves null-card semantics for ticketed responses", async () => {
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
        cardId: 123,
        rating: 3,
        ratingDescription: "Good",
      },
      next: {
        success: true,
        ticket: null,
        card: null,
        total: 0,
      },
    });

    const result = parseToolResult(
      await tool.rateCardAndGetNext(
        {
          card_id: 123,
          rating: 3,
          review_session_id: "session",
          review_ticket: "ticket",
        },
        mockContext,
      ),
    );

    expect(result.nextCard).toBeNull();
    expect(result.reviewSessionId).toBeNull();
    expect(result.reviewTicket).toBeNull();
    expect(result.replayed).toBe(false);
  });

  it("fails closed instead of falling back to answerCards on an unverified Anki version", async () => {
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
      await tool.rateCardAndGetNext(
        {
          card_id: 123,
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
    expect(getDueCardsTool.getNextDueCardData).not.toHaveBeenCalled();
  });

  it("retries the exact legacy queue race once after verifying the card", async () => {
    ankiClient.invoke
      .mockRejectedValueOnce(
        new AnkiConnectError(
          "AnkiConnect error: not at top of queue",
          "answerCards",
          "not at top of queue",
        ),
      )
      .mockResolvedValueOnce([{ cardId: 123 }])
      .mockResolvedValueOnce(true);
    getDueCardsTool.getNextDueCardData.mockResolvedValue({
      success: true,
      card: null,
      total: 0,
      message: "empty",
    });

    const result = parseToolResult(
      await tool.rateCardAndGetNext({ card_id: 123, rating: 3 }, mockContext),
    );

    expect(result.success).toBe(true);
    expect(ankiClient.invoke).toHaveBeenCalledTimes(3);
    expect(ankiClient.invoke).toHaveBeenNthCalledWith(2, "cardsInfo", {
      cards: [123],
    });
  });

  it("does not retry unrelated legacy failures", async () => {
    ankiClient.invoke.mockRejectedValueOnce(
      new AnkiConnectError("AnkiConnect error: boom", "answerCards", "boom"),
    );

    const result = parseToolResult(
      await tool.rateCardAndGetNext({ card_id: 123, rating: 3 }, mockContext),
    );

    expect(result.success).toBe(false);
    expect(ankiClient.invoke).toHaveBeenCalledTimes(1);
  });

  it("should rate the card and return the next card in one call", async () => {
    const nextCard = {
      cardId: 456,
      front: "Next front",
      back: "Next back",
      deckName: "Logic",
      modelName: "Basic",
      due: 10,
      interval: 0,
      factor: 2500,
    };
    ankiClient.invoke.mockResolvedValueOnce(true);
    getDueCardsTool.getNextDueCardData.mockResolvedValueOnce({
      success: true,
      card: nextCard,
      total: 2,
      message: "Found next due card",
    });

    const rawResult = await tool.rateCardAndGetNext(
      {
        card_id: 123,
        rating: 3,
        deck_name: "Logic",
        include_learning: true,
        include_new: true,
      },
      mockContext,
    );
    const result = parseToolResult(rawResult);

    expect(ankiClient.invoke).toHaveBeenCalledTimes(1);
    expect(ankiClient.invoke).toHaveBeenCalledWith("answerCards", {
      answers: [{ cardId: 123, ease: 3 }],
    });
    expect(getDueCardsTool.getNextDueCardData).toHaveBeenCalledWith({
      deck_name: "Logic",
      include_learning: true,
      include_new: true,
    });
    expect(result.success).toBe(true);
    expect(result.ratedCard.cardId).toBe(123);
    expect(result.nextCard).toEqual(nextCard);
  });

  it("should return null nextCard when the queue is empty", async () => {
    ankiClient.invoke.mockResolvedValueOnce(true);
    getDueCardsTool.getNextDueCardData.mockResolvedValueOnce({
      success: true,
      card: null,
      total: 0,
      message: "No cards are due for review",
    });

    const result = parseToolResult(
      await tool.rateCardAndGetNext({ card_id: 123, rating: 4 }, mockContext),
    );

    expect(result.success).toBe(true);
    expect(result.nextCard).toBeNull();
    expect(result.message).toContain("no cards");
  });

  it("should reject invalid ratings before touching Anki", async () => {
    const result = parseToolResult(
      await tool.rateCardAndGetNext({ card_id: 123, rating: 9 }, mockContext),
    );

    expect(ankiClient.invoke).not.toHaveBeenCalled();
    expect(getDueCardsTool.getNextDueCardData).not.toHaveBeenCalled();
    expect(result.success).toBe(false);
    expect(result.error).toContain("Invalid rating");
  });
});
