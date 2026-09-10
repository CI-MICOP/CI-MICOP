import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../apiClient", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { apiClient } from "../apiClient";
import { getDocumentById, listDocumentsByClaim, uploadDocument } from "../documentService";

describe("documentService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("uploadDocument() sends multipart FormData with claim_id, document_type and file", async () => {
    const created = {
      Document_ID: "DOC-20260910-ABCDEF",
      Claim_ID: "CLM-ABC123",
      Document_Type: "FIR",
      Document_Name: "fir.pdf",
      Document_Status: "Submitted",
      Verification_Status: "Pending",
    };
    apiClient.post.mockResolvedValueOnce({ data: created });
    const file = new File(["%PDF-1.4"], "fir.pdf", { type: "application/pdf" });

    const result = await uploadDocument("CLM-ABC123", "fir_copy", file);

    expect(apiClient.post).toHaveBeenCalledTimes(1);
    const [url, body, config] = apiClient.post.mock.calls[0];
    expect(url).toBe("/documents");
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("claim_id")).toBe("CLM-ABC123");
    expect(body.get("document_type")).toBe("fir_copy");
    expect(body.get("file")).toBe(file);
    // Content-Type/boundary must be left for Axios/the browser, never set manually.
    expect(config?.headers?.["Content-Type"]).toBeUndefined();
    expect(result).toEqual(created);
  });

  it("successful upload returns the created document metadata", async () => {
    apiClient.post.mockResolvedValueOnce({ data: { Document_ID: "DOC-1", Document_Status: "Submitted" } });
    const file = new File(["x"], "a.jpg");
    const result = await uploadDocument("CLM-1", "accident_photos", file);
    expect(result.Document_ID).toBe("DOC-1");
  });

  it("propagates upload errors to the caller", async () => {
    const error = { response: { status: 400, data: { detail: "Unsupported file type." } } };
    apiClient.post.mockRejectedValueOnce(error);
    const file = new File(["x"], "a.exe");
    await expect(uploadDocument("CLM-1", "fir_copy", file)).rejects.toBe(error);
  });

  it("listDocumentsByClaim() calls GET /documents with claim_id param", async () => {
    apiClient.get.mockResolvedValueOnce({ data: [] });
    await listDocumentsByClaim("CLM-1");
    expect(apiClient.get).toHaveBeenCalledWith("/documents", { params: { claim_id: "CLM-1" } });
  });

  it("getDocumentById() calls GET /documents/:id", async () => {
    apiClient.get.mockResolvedValueOnce({ data: { Document_ID: "DOC-1" } });
    await getDocumentById("DOC-1");
    expect(apiClient.get).toHaveBeenCalledWith("/documents/DOC-1");
  });
});
