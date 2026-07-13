import { Test, TestingModule } from "@nestjs/testing";
import { AnkiConnectClient } from "../../../../clients/anki-connect.client";
import { ChatReviewRecoveryStore } from "../../../../services/chat-review-recovery.store";
import {
  createMockContext,
  parseToolResult,
} from "../../../../../test-fixtures/test-helpers";
import { ResumeActiveReviewTool } from "../resume-active-review.tool";

describe("ResumeActiveReviewTool", () => {
  let tool: ResumeActiveReviewTool;
  let client: any;
  let store: any;
  const entry = {
    endpointHash: "endpoint",
    generationHash: "generation",
    protocol: "chat-review/v1",
    reviewSessionId: "original-session",
    deckName: "Logic",
    cardId: 123,
    createdAt: new Date().toISOString(),
    lastSuccessAt: new Date().toISOString(),
    originPid: process.pid,
    processNonce: "old-process",
    sessionHash: "redacted",
    state: "recovery-required",
  };

  beforeEach(async () => {
    client = {
      endpointIdentifierHash: "endpoint",
      getChatReviewCapabilities: jest.fn().mockResolvedValue({
        protocol: "chat-review/v1",
        supportsTickets: true,
        supportsRecovery: true,
        generationHash: "generation",
        ankiVersionVerified: true,
      }),
      invoke: jest.fn(),
    };
    store = {
      find: jest.fn().mockResolvedValue(entry),
      save: jest.fn(),
      clearSession: jest.fn(),
      markSession: jest.fn(),
    };
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ResumeActiveReviewTool,
        { provide: AnkiConnectClient, useValue: client },
        { provide: ChatReviewRecoveryStore, useValue: store },
      ],
    }).compile();
    tool = module.get(ResumeActiveReviewTool);
  });

  it("reissues next with the original session and never answers", async () => {
    client.invoke.mockResolvedValue({
      success: true,
      ticket: "reissued-ticket",
      total: 1,
      card: {
        cardId: 123,
        front: "question",
        back: "answer",
        deckName: "Logic",
        modelName: "Basic",
        due: 1,
        interval: 2,
        factor: 2500,
      },
    });
    const result = await tool.resumeActiveReview(
      { confirm_resume: true, deck_name: "Logic", expected_card_id: 123 },
      createMockContext(),
    );

    expect(result).toMatchObject({
      success: true,
      outcomeCode: "REVIEW_RESUMED",
      reviewSessionId: "original-session",
      reviewTicket: "reissued-ticket",
    });
    expect(client.invoke).toHaveBeenCalledWith("chatReviewNext", {
      sessionId: "original-session",
      deckName: "Logic",
      includeLearning: true,
      includeNew: true,
    });
    expect(client.invoke).not.toHaveBeenCalledWith(
      "chatReviewAnswer",
      expect.anything(),
    );
  });

  it("fails before contacting Anki on expected-card mismatch", async () => {
    const result = await tool.resumeActiveReview(
      { confirm_resume: true, expected_card_id: 999 },
      createMockContext(),
    );
    expect(client.invoke).not.toHaveBeenCalled();
    expect(parseToolResult(result)).toMatchObject({ success: false });
    expect(store.markSession).toHaveBeenCalledWith(
      "original-session",
      "recovery-required",
    );
  });
});
