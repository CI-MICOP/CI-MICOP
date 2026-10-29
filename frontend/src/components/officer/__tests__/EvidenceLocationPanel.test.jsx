import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../services/officerService", () => ({
  getClaimEvidenceLocations: vi.fn(),
}));

import { getClaimEvidenceLocations } from "../../../services/officerService";
import EvidenceLocationPanel from "../EvidenceLocationPanel";

const GPS_ITEM = {
  Evidence_ID: "EVD-1",
  Evidence_Type: "Vehicle Damage Close-up",
  capture: {
    client: { latitude: 13.0827, longitude: 80.2707, accuracy_m: 12, address_label: null },
    checks: { location_status: "captured" },
  },
  qualifying_capture: true,
};

const MAP_ITEM = {
  Evidence_ID: "EVD-2",
  Evidence_Type: "Overall Vehicle Condition",
  capture: {
    client: { latitude: 13.09, longitude: 80.28, accuracy_m: null, address_label: "T. Nagar, Chennai" },
    checks: { location_status: "map_selected" },
  },
  qualifying_capture: true,
};

describe("EvidenceLocationPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a GPS-verified item distinctly from a map-selected item", async () => {
    getClaimEvidenceLocations.mockResolvedValue({ Claim_ID: "CLM-1", evidence: [GPS_ITEM, MAP_ITEM] });
    render(<EvidenceLocationPanel claimId="CLM-1" />);

    await screen.findByText("Evidence Location");
    const gpsRow = screen.getByText("Vehicle Damage Close-up").closest("li");
    expect(within(gpsRow).getByText("GPS verified")).toBeInTheDocument();
    expect(within(gpsRow).getByText(/13\.082700, 80\.270700/)).toBeInTheDocument();

    const mapRow = screen.getByText("Overall Vehicle Condition").closest("li");
    expect(within(mapRow).getByText("Map-selected — GPS not verified")).toBeInTheDocument();
    expect(within(mapRow).getByText(/T\. Nagar, Chennai/)).toBeInTheDocument();
    // Never shown as GPS verified.
    expect(within(mapRow).queryByText("GPS verified")).not.toBeInTheDocument();
  });

  it("shows an empty state when the claim has no surveyor-captured photos", async () => {
    getClaimEvidenceLocations.mockResolvedValue({ Claim_ID: "CLM-1", evidence: [] });
    render(<EvidenceLocationPanel claimId="CLM-1" />);
    expect(await screen.findByText(/no surveyor-captured photos/i)).toBeInTheDocument();
  });

  it("shows whether each item counts toward the surveyor-photo requirement", async () => {
    getClaimEvidenceLocations.mockResolvedValue({
      Claim_ID: "CLM-1",
      evidence: [{ ...GPS_ITEM, qualifying_capture: false, capture: { ...GPS_ITEM.capture, checks: { location_status: "accuracy_insufficient" } } }],
    });
    render(<EvidenceLocationPanel claimId="CLM-1" />);
    await screen.findByText("Vehicle Damage Close-up");
    expect(screen.getByText("GPS accuracy insufficient")).toBeInTheDocument();
    expect(screen.getByText("Does not count")).toBeInTheDocument();
  });
});
