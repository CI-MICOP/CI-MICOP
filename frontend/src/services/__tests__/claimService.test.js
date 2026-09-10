import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../apiClient", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { apiClient } from "../apiClient";
import { createClaim, getClaimById, listClaims } from "../claimService";

describe("claimService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("createClaim() calls POST /claims with the given payload and never injects a Customer_ID", async () => {
    const payload = {
      Policy_ID: "POL-1",
      Vehicle_ID: "VEH-1",
      Claim_Date: "2026-09-01",
      Claim_Type: "Own Damage",
      Claim_Amount: "50000",
      Claim_Description: "Front bumper damage.",
      Place_of_Accident: "Chennai",
      Accident_Pincode: "600001",
    };
    const created = { Claim_ID: "CLM-ABC123", Claim_Number: "CLM-2026-DEADBEEF", Claim_Status: "Under Review" };
    apiClient.post.mockResolvedValueOnce({ data: created });

    const result = await createClaim(payload);

    expect(apiClient.post).toHaveBeenCalledWith("/claims", payload);
    expect(payload.Customer_ID).toBeUndefined();
    expect(result).toEqual(created);
  });

  it("listClaims() calls GET /claims", async () => {
    apiClient.get.mockResolvedValueOnce({ data: [] });
    await listClaims();
    expect(apiClient.get).toHaveBeenCalledWith("/claims", { params: {} });
  });

  it("getClaimById() calls GET /claims/:id", async () => {
    apiClient.get.mockResolvedValueOnce({ data: { Claim_ID: "CLM-1" } });
    await getClaimById("CLM-1");
    expect(apiClient.get).toHaveBeenCalledWith("/claims/CLM-1");
  });
});
