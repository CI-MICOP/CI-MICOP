import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SurveyorSupportPage from "../SupportPage";

describe("SurveyorSupportPage", () => {
  it("no longer shows Chat with Support, and keeps Contact Support and the FAQs", () => {
    render(<SurveyorSupportPage />);
    expect(screen.queryByText("Chat with Support")).not.toBeInTheDocument();
    expect(screen.queryByText(/live chat/i)).not.toBeInTheDocument();
    expect(screen.getByText("Contact Support")).toBeInTheDocument();
    expect(screen.getByText("FAQs")).toBeInTheDocument();
    expect(screen.getByText("How do I submit a survey report?")).toBeInTheDocument();
  });

  it("lets Contact Support span the full width, leaving no empty column", () => {
    render(<SurveyorSupportPage />);
    expect(screen.getByText("Contact Support").closest(".lg\\:col-span-2")).not.toBeNull();
  });

  it("refers to the current navigation, not the removed sidebar", () => {
    render(<SurveyorSupportPage />);
    expect(screen.queryByText(/sidebar/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Open "Survey Reports" on the menu/)).toBeInTheDocument();
    expect(screen.queryByText(/"More"/)).not.toBeInTheDocument();
  });
});
