import { describe, expect, it } from "vitest";

import { formatDate } from "../format";

describe("formatDate", () => {
  it("shows a date-only value as that calendar date in every time zone", () => {
    // Parsed as UTC midnight; formatting in UTC keeps it on the same day
    // (west of UTC it used to show the previous day).
    expect(formatDate("2026-10-28")).toBe("28 Oct 2026");
    expect(formatDate("2026-01-01")).toBe("01 Jan 2026");
  });

  it("still handles missing and unreadable values", () => {
    expect(formatDate(null)).toBe("-");
    expect(formatDate("not a date")).toBe("not a date");
  });
});
