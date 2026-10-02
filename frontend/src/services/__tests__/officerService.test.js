import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../apiClient", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { apiClient } from "../apiClient";
import { analyzeClaimDocuments, checkClaimConsistency } from "../officerService";

describe("officerService - document consistency", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("analyzeClaimDocuments() calls POST /officer/claims/{id}/documents/analyze with no body", async () => {
    const data = { Claim_ID: "CLM-1", documents_analyzed: 0, documents: [] };
    apiClient.post.mockResolvedValueOnce({ data });

    const result = await analyzeClaimDocuments("CLM-1");

    expect(apiClient.post).toHaveBeenCalledWith("/officer/claims/CLM-1/documents/analyze");
    expect(result).toEqual(data);
  });

  it("checkClaimConsistency() calls POST /officer/claims/{id}/documents/semantic-consistency with no body", async () => {
    const data = { Claim_ID: "CLM-1", narrative: {}, deterministic: {} };
    apiClient.post.mockResolvedValueOnce({ data });

    const result = await checkClaimConsistency("CLM-1");

    expect(apiClient.post).toHaveBeenCalledWith("/officer/claims/CLM-1/documents/semantic-consistency");
    expect(result).toEqual(data);
  });
});
