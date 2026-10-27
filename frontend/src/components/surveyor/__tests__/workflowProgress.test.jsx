import { act, fireEvent, render, renderHook, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import ClaimStepNav from "../ClaimStepNav";
import ClaimTabs from "../ClaimTabs";
import { useScheduleReached } from "../useSurveyorClaim";
import { STEP_STATE, inspectionIssues, lockedReason, workflowProgress } from "../workflowProgress";
import { COMPLETE_INSPECTION, schedule, workflow } from "./workflowFixture";

const detail = (wf, inspections = [COMPLETE_INSPECTION]) => ({ inspections, workflow: wf });

describe("workflowProgress (from the server's workflow summary)", () => {
  it("locks every step except Claim Details before the scheduled date", () => {
    const progress = workflowProgress(detail(workflow("new", { schedule: schedule({ reached: false }) })), "EMP-1");
    expect(progress.scheduleReached).toBe(false);
    expect(progress.canEdit).toBe(false);
    expect([...progress.unlocked]).toEqual(["details"]);
    expect(progress.steps.inspection).toBe(STEP_STATE.LOCKED_SCHEDULE);
    expect(lockedReason(progress)).toMatch(/will become available on 28 October 2026/);
  });

  it("opens the steps in order as the server reports them complete", () => {
    const states = (stage) => workflowProgress(detail(workflow(stage)), "EMP-1").steps;
    expect(states("new")).toMatchObject({
      inspection: STEP_STATE.IN_PROGRESS,
      damage: STEP_STATE.LOCKED_PREREQUISITE,
      evidence: STEP_STATE.LOCKED_PREREQUISITE,
      report: STEP_STATE.LOCKED_PREREQUISITE,
    });
    expect(states("inspection")).toMatchObject({
      inspection: STEP_STATE.COMPLETED,
      damage: STEP_STATE.NOT_STARTED,
      evidence: STEP_STATE.LOCKED_PREREQUISITE,
    });
    expect(states("evidence")).toMatchObject({ evidence: STEP_STATE.COMPLETED, report: STEP_STATE.IN_PROGRESS });
  });

  it("treats a submitted report as final - every step open for review, none editable", () => {
    const progress = workflowProgress(detail(workflow("submitted")), "EMP-1");
    expect(progress.submitted).toBe(true);
    expect(progress.canEdit).toBe(false);
    expect(progress.reportAvailable).toBe(true);
    expect(Object.values(progress.steps).filter((s) => s === STEP_STATE.SUBMITTED)).toHaveLength(4);
  });

  it("lets a live schedule value override the value loaded with the page", () => {
    const wf = workflow("new", { schedule: schedule({ reached: false }) });
    expect(workflowProgress(detail(wf), "EMP-1", true).unlocked.has("inspection")).toBe(true);
  });

  it("has nothing to offer without an assigned inspection", () => {
    const progress = workflowProgress({ inspections: [], workflow: null }, "EMP-1");
    expect(progress.canEdit).toBe(false);
    expect([...progress.unlocked]).toEqual(["details"]);
    expect(lockedReason(progress)).toMatch(/no inspection is assigned/i);
  });

  it("separates missing (draft) values from invalid ones", () => {
    const kinds = Object.fromEntries(
      inspectionIssues({ ...COMPLETE_INSPECTION, Vehicle_Condition: "Pending", Repair_Recommendation: "Damaged", Parts_Required: "-1" }).map(
        (issue) => [issue.field, issue.kind]
      )
    );
    expect(kinds).toEqual({ Vehicle_Condition: "missing", Repair_Recommendation: "invalid", Parts_Required: "invalid" });
    expect(inspectionIssues(COMPLETE_INSPECTION)).toEqual([]);
  });
});

describe("useScheduleReached", () => {
  afterEach(() => vi.useRealTimers());

  it("opens at the scheduled time without a page refresh, using the server clock", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-27T18:29:00Z")); // 23:59 IST on 27 Oct
    // The server's clock is the same as this device's here; the start is 00:00 IST.
    const sched = schedule({ reached: false, serverTime: "2026-10-27T23:59:00+05:30" });
    const { result } = renderHook(() => useScheduleReached(sched, 0));
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(59 * 1000));
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(2 * 1000));
    expect(result.current).toBe(true);
  });

  it("follows the server clock when this device's clock is wrong", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-27T10:00:00Z")); // device is ~8.5 hours behind
    const sched = schedule({ reached: false });
    const offset = Date.parse("2026-10-27T23:59:30+05:30") - Date.now(); // server reported 23:59:30 IST
    const { result } = renderHook(() => useScheduleReached(sched, offset));
    expect(result.current).toBe(false);
    act(() => vi.advanceTimersByTime(31 * 1000));
    expect(result.current).toBe(true);
  });
});

describe("ClaimTabs", () => {
  it("shows why steps are locked and marks completed ones", () => {
    const progress = workflowProgress(detail(workflow("inspection")), "EMP-1");
    render(
      <MemoryRouter>
        <ClaimTabs claimId="CLM-1" progress={progress} />
      </MemoryRouter>
    );
    const tabs = within(screen.getByRole("navigation", { name: "Claim sections" }));
    expect(tabs.getByRole("link", { name: "Inspection" })).toHaveAttribute("title", "Completed");
    expect(tabs.getByRole("link", { name: "Vehicle Damage" })).toBeInTheDocument();
    for (const locked of ["Evidence", "Survey Report"]) {
      expect(tabs.queryByRole("link", { name: locked })).not.toBeInTheDocument();
      expect(tabs.getByText(locked)).toHaveAttribute("title", "Complete the earlier steps first");
    }
  });

  it("locks every step but Claim Details until the scheduled date", () => {
    const progress = workflowProgress(detail(workflow("new", { schedule: schedule({ reached: false }) })), "EMP-1");
    render(
      <MemoryRouter>
        <ClaimTabs claimId="CLM-1" progress={progress} />
      </MemoryRouter>
    );
    const tabs = within(screen.getByRole("navigation", { name: "Claim sections" }));
    expect(tabs.getAllByRole("link")).toHaveLength(1);
    expect(tabs.getByText("Inspection")).toHaveAttribute("title", "Available from the scheduled inspection date");
  });
});

describe("ClaimStepNav", () => {
  afterEach(() => vi.restoreAllMocks());

  function renderNav(props) {
    render(
      <MemoryRouter initialEntries={["/surveyor/claims/CLM-1/damage"]}>
        <Routes>
          <Route path="/surveyor/claims/:claimId/damage" element={<ClaimStepNav claimId="CLM-1" current="damage" {...props} />} />
          <Route path="/surveyor/claims/:claimId/evidence" element={<p>Evidence step</p>} />
          <Route path="/surveyor/claims/:claimId/inspection" element={<p>Inspection step</p>} />
        </Routes>
      </MemoryRouter>
    );
  }

  it("disables Next and explains why while the step is blocked", () => {
    const onNext = vi.fn();
    renderNav({ onNext, blockedReason: "Save at least one damage record to continue." });
    const next = screen.getByRole("button", { name: /next/i });
    expect(next).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Save at least one damage record to continue.");
    fireEvent.click(next);
    expect(onNext).not.toHaveBeenCalled();
  });

  it("stays on the step and shows the reason when the check fails", async () => {
    renderNav({ onNext: async () => "The record could not be saved." });
    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The record could not be saved.");
    expect(screen.queryByText("Evidence step")).not.toBeInTheDocument();
  });

  it("runs the check once for repeated clicks, then moves on", async () => {
    let finish;
    const onNext = vi.fn(() => new Promise((resolve) => (finish = resolve)));
    renderNav({ onNext });
    const next = screen.getByRole("button", { name: /next/i });
    fireEvent.click(next);
    fireEvent.click(next);
    expect(onNext).toHaveBeenCalledTimes(1);
    expect(next).toBeDisabled();
    finish(true);
    expect(await screen.findByText("Evidence step")).toBeInTheDocument();
  });

  it("asks before Back discards unsaved changes", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderNav({ onNext: async () => true, hasUnsavedChanges: true });
    fireEvent.click(screen.getByRole("link", { name: /back/i }));
    expect(confirm).toHaveBeenCalled();
    expect(screen.queryByText("Inspection step")).not.toBeInTheDocument();

    confirm.mockReturnValue(true);
    fireEvent.click(screen.getByRole("link", { name: /back/i }));
    expect(screen.getByText("Inspection step")).toBeInTheDocument();
  });
});
