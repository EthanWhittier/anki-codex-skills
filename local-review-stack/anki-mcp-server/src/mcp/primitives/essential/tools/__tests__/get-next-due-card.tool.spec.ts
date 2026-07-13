import { Test, TestingModule } from "@nestjs/testing";
import { GetNextDueCardTool } from "../get-next-due-card.tool";
import { GetDueCardsTool } from "../get-due-cards.tool";
import { AnkiConnectClient } from "../../../../clients/anki-connect.client";
import { ChatReviewRecoveryStore } from "../../../../services/chat-review-recovery.store";
import {
  createMockContext,
  parseToolResult,
} from "../../../../../test-fixtures/test-helpers";

describe("GetNextDueCardTool", () => {
  let tool: GetNextDueCardTool;
  let getDueCardsTool: jest.Mocked<GetDueCardsTool>;
  let ankiClient: jest.Mocked<AnkiConnectClient>;
  let recoveryStore: jest.Mocked<ChatReviewRecoveryStore>;
  let mockContext: any;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        GetNextDueCardTool,
        {
          provide: AnkiConnectClient,
          useValue: {
            invoke: jest.fn(),
            getChatReviewCapabilities: jest.fn(),
            endpointIdentifierHash: "endpoint-hash",
          },
        },
        {
          provide: ChatReviewRecoveryStore,
          useValue: {
            find: jest.fn().mockResolvedValue(null),
            belongsToCurrentProcess: jest.fn().mockReturnValue(false),
            save: jest.fn(),
            clearSession: jest.fn(),
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

    tool = module.get<GetNextDueCardTool>(GetNextDueCardTool);
    getDueCardsTool = module.get(
      GetDueCardsTool,
    ) as jest.Mocked<GetDueCardsTool>;
    ankiClient = module.get(
      AnkiConnectClient,
    ) as jest.Mocked<AnkiConnectClient>;
    recoveryStore = module.get(
      ChatReviewRecoveryStore,
    ) as jest.Mocked<ChatReviewRecoveryStore>;
    ankiClient.getChatReviewCapabilities.mockResolvedValue(null);
    mockContext = createMockContext();
  });

  it("offers explicit recovery instead of creating a competing session", async () => {
    ankiClient.getChatReviewCapabilities.mockResolvedValue({
      protocol: "chat-review/v1",
      supportsTickets: true,
      supportsIdempotentReplay: true,
      supportsRecovery: true,
      ticketProtocolVersion: "chat-review/v1",
      generationHash: "generation-hash",
      ankiVersion: "25.09.2",
      ankiVersionVerified: true,
      testedAnkiVersions: ["25.09.2"],
      fsrs: { enabled: true, scheduler: "fsrs" },
    });
    recoveryStore.find.mockResolvedValue({
      protocol: "chat-review/v1",
      endpointHash: "endpoint-hash",
      generationHash: "generation-hash",
      reviewSessionId: "previous-session",
      deckName: "Logic",
      cardId: 123,
      createdAt: new Date().toISOString(),
      lastSuccessAt: new Date().toISOString(),
      originPid: 1,
      processNonce: "previous-process",
      sessionHash: "redacted",
      state: "recovery-required",
    });

    const result = await tool.getNextDueCard(
      { deck_name: "Logic", include_learning: true, include_new: true },
      mockContext,
    );

    expect(result).toMatchObject({
      success: false,
      outcomeCode: "REVIEW_RECOVERY_AVAILABLE",
      reviewSessionId: null,
      reviewTicket: null,
    });
    expect(ankiClient.invoke).not.toHaveBeenCalled();
  });

  it("should request the optimized next due card selector", async () => {
    const card = {
      cardId: 1777960926642,
      front: "Give the letter for Some S are P",
      back: "I",
      deckName: "Logic",
      modelName: "Basic",
      due: 857,
      interval: 0,
      factor: 2500,
    };
    getDueCardsTool.getNextDueCardData.mockResolvedValueOnce({
      success: true,
      card,
      total: 3,
      message: "Found next due card",
    });

    const result = await tool.getNextDueCard(
      {
        deck_name: "Logic",
        include_learning: true,
        include_new: true,
      },
      mockContext,
    );

    expect(getDueCardsTool.getNextDueCardData).toHaveBeenCalledWith({
      deck_name: "Logic",
      include_learning: true,
      include_new: true,
    });
    expect(result).toEqual({
      success: true,
      card,
      total: 3,
      message: "Found next due card",
      reviewSessionId: null,
      reviewTicket: null,
    });
  });

  it("should return null card when no cards are available", async () => {
    getDueCardsTool.getNextDueCardData.mockResolvedValueOnce({
      success: true,
      card: null,
      total: 0,
      message: "No cards are due for review",
    });

    const result = await tool.getNextDueCard({}, mockContext);

    expect(result).toEqual({
      success: true,
      card: null,
      total: 0,
      message: "No cards are due for review",
      reviewSessionId: null,
      reviewTicket: null,
    });
  });

  it("uses chat-review tickets and propagates opaque state", async () => {
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
      ticket: "secret-ticket",
      card: {
        cardId: 123,
        front: "front",
        back: "back",
        deckName: "Logic",
        modelName: "Basic",
        due: 1,
        interval: 0,
        factor: 2500,
      },
      total: 2,
    });

    const result = await tool.getNextDueCard(
      {
        deck_name: "Logic",
        include_learning: true,
        include_new: true,
        review_session_id: "secret-session",
      },
      mockContext,
    );

    expect(ankiClient.invoke).toHaveBeenCalledWith("chatReviewNext", {
      sessionId: "secret-session",
      deckName: "Logic",
      includeLearning: true,
      includeNew: true,
    });
    expect(result.reviewSessionId).toBe("secret-session");
    expect(result.reviewTicket).toBe("secret-ticket");
    expect(getDueCardsTool.getNextDueCardData).not.toHaveBeenCalled();
  });

  it("compacts ticketed rendered HTML without changing ticket state", async () => {
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
      ticket: "secret-ticket",
      card: {
        cardId: 123,
        front: "<style>.card { color: red; }</style><div>Question?</div>",
        back: "<style>.card { color: red; }</style><div>Question?</div><hr><div>Answer.</div>",
        deckName: "Logic",
        modelName: "Basic",
        due: 1,
        interval: 0,
        factor: 2500,
      },
      total: 2,
    });

    const result = await tool.getNextDueCard(
      { review_session_id: "secret-session" },
      mockContext,
    );

    expect(result.card).toMatchObject({
      cardId: 123,
      front: "Question?",
      back: "Answer.",
    });
    expect(result.reviewSessionId).toBe("secret-session");
    expect(result.reviewTicket).toBe("secret-ticket");
    expect(JSON.stringify(result.card)).not.toContain("secret-");
  });

  it("fails closed on an unverified Anki version", async () => {
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

    const result = parseToolResult(await tool.getNextDueCard({}, mockContext));

    expect(result.success).toBe(false);
    expect(result.error).toContain("ANKI_VERSION_UNVERIFIED");
    expect(ankiClient.invoke).not.toHaveBeenCalled();
    expect(getDueCardsTool.getNextDueCardData).not.toHaveBeenCalled();
  });

  it("should forward errors from get_due_cards", async () => {
    const errorResult = {
      success: false,
      error: "Cannot connect to Anki",
      action: "findCards",
    };
    getDueCardsTool.getNextDueCardData.mockResolvedValueOnce(errorResult);

    const result = await tool.getNextDueCard({}, mockContext);

    expect(result).toBe(errorResult);
  });
});
