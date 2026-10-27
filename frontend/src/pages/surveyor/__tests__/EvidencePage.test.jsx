// Camera, geolocation, canvas and video are mocked here: these tests check
// the application's logic, not real device or browser camera behaviour.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../hooks/useAuth", () => ({ useAuth: () => ({ user: { Employee_ID: "EMP-1" } }) }));
vi.mock("../../../services/claimService", () => ({
  getClaimById: vi.fn(),
}));
vi.mock("../../../services/surveyorService", () => ({
  getAssignedClaimDetail: vi.fn(),
  createEvidenceCapture: vi.fn(),
  getEvidenceImage: vi.fn(),
}));

import { COMPLETE_INSPECTION, schedule, workflow } from "../../../components/surveyor/__tests__/workflowFixture";
import { getClaimById } from "../../../services/claimService";
import { createEvidenceCapture, getAssignedClaimDetail, getEvidenceImage } from "../../../services/surveyorService";
import EvidencePage from "../EvidencePage";

const CLAIM = { Claim_ID: "CLM-1", Claim_Number: "CLM-2026-AAAA" };
const TYPES = ["Vehicle Damage Close-up", "Overall Vehicle Condition", "Damage Location and Extent", "Accident Scene / Surroundings"];

const CAPTURE = {
  capture_method: "in_app_camera",
  client: { captured_at: "2026-10-28T04:30:00+00:00", latitude: 13.0827, longitude: 80.2707, accuracy_m: 12, error: null },
  server: { role: "surveyor", received_at: "2026-10-28T10:00:05+05:30", surveyor_employee_id: "EMP-1", inspection_id: "INSP-1" },
  checks: { location_status: "captured", max_accuracy_m: 100, client_time_status: "consistent" },
};

const SAVED_PHOTO = {
  Evidence_ID: "EVD-1",
  Claim_ID: "CLM-1",
  Evidence_Type: "Vehicle Damage Close-up",
  File_Name: "camera-capture-20261028-100005.jpg",
  Evidence_Date: "2026-10-28",
  Evidence_Source: "Surveyor",
  Verification_Status: "Pending",
  capture: CAPTURE,
  qualifying_capture: true,
};

const detail = ({ evidence = [], wf = workflow("damage") } = {}) => ({
  inspections: [COMPLETE_INSPECTION],
  vehicle_damage: [{ Damage_ID: "DMG-1" }],
  evidence,
  workflow: { ...wf, schedule: { ...wf.schedule, scheduled_date: "2026-01-01" } },
});
const completed = (evidence = [SAVED_PHOTO]) => detail({ evidence, wf: workflow("evidence", { qualifying_photo_count: evidence.length }) });

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/surveyor/claims/CLM-1/evidence"]}>
      <Routes>
        <Route path="/surveyor/claims/:claimId/evidence" element={<EvidencePage />} />
        <Route path="/surveyor/claims/:claimId/report" element={<p>Survey Report step</p>} />
      </Routes>
    </MemoryRouter>
  );
}

const nextButton = () => screen.getByRole("button", { name: /next/i });
const imagesCard = () => screen.getByRole("heading", { name: /^Images \(\d+\)$/ }).closest("div.rounded-card");
const unsaved = () => screen.queryAllByRole("listitem", { name: /unsaved image/i });

// ---------------------------------------------------------------- device mocks

const originals = {};
let stopTrack;

function mockCamera({ failWith } = {}) {
  stopTrack = vi.fn();
  const getUserMedia = failWith
    ? vi.fn().mockRejectedValue(Object.assign(new Error("camera"), { name: failWith }))
    : vi.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] });
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
  return getUserMedia;
}

function mockLocation(...results) {
  const queue = [...results];
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: {
      getCurrentPosition: vi.fn((ok, fail) => {
        const result = queue.length > 1 ? queue.shift() : queue[0];
        if (result.code) fail({ code: result.code });
        else ok({ coords: result });
      }),
    },
  });
}

const GOOD_FIX = { latitude: 13.0827, longitude: 80.2707, accuracy: 12 };

beforeEach(() => {
  vi.clearAllMocks();
  getClaimById.mockResolvedValue(CLAIM);
  getEvidenceImage.mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" }));
  originals.getContext = HTMLCanvasElement.prototype.getContext;
  originals.toBlob = HTMLCanvasElement.prototype.toBlob;
  originals.play = HTMLMediaElement.prototype.play;
  originals.createObjectURL = URL.createObjectURL;
  originals.revokeObjectURL = URL.revokeObjectURL;
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({ drawImage: vi.fn() }));
  HTMLCanvasElement.prototype.toBlob = vi.fn((callback) => callback(new Blob(["jpeg-bytes"], { type: "image/jpeg" })));
  HTMLMediaElement.prototype.play = vi.fn(() => Promise.resolve());
  Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", { configurable: true, get: () => 1280 });
  Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", { configurable: true, get: () => 720 });
  let n = 0;
  URL.createObjectURL = vi.fn(() => `blob:preview-${++n}`);
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  cleanup(); // unmount (releasing the camera and previews) before the mocks go
  HTMLCanvasElement.prototype.getContext = originals.getContext;
  HTMLCanvasElement.prototype.toBlob = originals.toBlob;
  HTMLMediaElement.prototype.play = originals.play;
  delete HTMLVideoElement.prototype.videoWidth;
  delete HTMLVideoElement.prototype.videoHeight;
  URL.createObjectURL = originals.createObjectURL;
  URL.revokeObjectURL = originals.revokeObjectURL;
  delete navigator.mediaDevices;
  delete navigator.geolocation;
  vi.restoreAllMocks();
});

async function openCamera() {
  fireEvent.click(await screen.findByRole("button", { name: /open camera/i }));
  expect(await screen.findByTestId("camera-preview")).toBeInTheDocument();
}

async function capture() {
  await act(async () => fireEvent.click(screen.getByRole("button", { name: /^capture$/i })));
}

describe("EvidencePage - the capture form", () => {
  it("shows Evidence Type and Date with the camera area - no source field, no Accident Photo card, no file picker", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    const { container } = renderPage();
    const typeSelect = await screen.findByLabelText(/evidence type/i);
    expect(within(typeSelect).getAllByRole("option").map((o) => o.textContent)).toEqual(TYPES);
    expect(screen.getByLabelText(/evidence date/i)).toHaveAttribute("type", "date");
    expect(screen.queryByLabelText(/evidence source/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^accident photo$/i)).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Capture Your Image" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open camera/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Images (0)" })).toBeInTheDocument();
    expect(container.querySelector('input[type="file"]')).toBeNull();
    expect(nextButton()).toBeDisabled();
  });

  it("keeps every captured photo, with its own type and date, and counts them", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    mockCamera();
    mockLocation(GOOD_FIX);
    renderPage();
    await openCamera();
    await capture();
    // The next photo takes the form's current type.
    fireEvent.change(screen.getAllByLabelText(/evidence type/i)[0], { target: { value: "Accident Scene / Surroundings" } });
    await capture();

    expect(screen.getByRole("heading", { name: "Images (2)" })).toBeInTheDocument();
    const [first, second] = unsaved();
    expect(within(first).getByLabelText(/evidence type/i)).toHaveValue("Vehicle Damage Close-up");
    expect(within(second).getByLabelText(/evidence type/i)).toHaveValue("Accident Scene / Surroundings");
    // Changing one photo's type does not touch the other.
    fireEvent.change(within(first).getByLabelText(/evidence type/i), { target: { value: "Overall Vehicle Condition" } });
    expect(within(second).getByLabelText(/evidence type/i)).toHaveValue("Accident Scene / Surroundings");
    expect(within(first).getByText(/location captured/i)).toBeInTheDocument();
    expect(nextButton()).toBeDisabled(); // unsaved images block Next
  });

  it("saves each photo once with its own metadata, then lists them as saved", async () => {
    getAssignedClaimDetail.mockResolvedValueOnce(detail()).mockResolvedValue(completed([SAVED_PHOTO, { ...SAVED_PHOTO, Evidence_ID: "EVD-2" }]));
    mockCamera();
    mockLocation(GOOD_FIX);
    createEvidenceCapture.mockResolvedValue(SAVED_PHOTO);
    renderPage();
    await openCamera();
    await capture();
    await capture();
    const [first] = unsaved();
    fireEvent.change(within(first).getByLabelText(/evidence type/i), { target: { value: "Damage Location and Extent" } });
    fireEvent.change(within(first).getByLabelText(/evidence date/i), { target: { value: "2026-01-05" } });

    const save = screen.getByRole("button", { name: "Save 2 images" });
    fireEvent.click(save);
    fireEvent.click(save); // a repeated click while saving
    await waitFor(() => expect(createEvidenceCapture).toHaveBeenCalledTimes(2));
    const [claimId, firstPayload] = createEvidenceCapture.mock.calls[0];
    expect(claimId).toBe("CLM-1");
    expect(firstPayload).toMatchObject({ evidenceType: "Damage Location and Extent", evidenceDate: "2026-01-05", latitude: 13.0827, accuracy: 12 });
    expect(createEvidenceCapture.mock.calls[1][1]).toMatchObject({ evidenceType: "Vehicle Damage Close-up" });
    expect(firstPayload.photo).toBeInstanceOf(Blob);

    expect(await screen.findByText("2 photos saved.")).toBeInTheDocument();
    await waitFor(() => expect(unsaved()).toHaveLength(0));
    expect(screen.getByRole("heading", { name: "Images (2)" })).toBeInTheDocument();
    expect(within(imagesCard()).getAllByText("Saved")).toHaveLength(2);
    await waitFor(() => expect(getEvidenceImage).toHaveBeenCalledWith("EVD-1"));
    fireEvent.click(nextButton());
    expect(await screen.findByText("Survey Report step")).toBeInTheDocument();
  });

  it("removes or retakes an unsaved photo, keeping its metadata for the retake", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    mockCamera();
    mockLocation(GOOD_FIX);
    renderPage();
    await openCamera();
    await capture();
    await capture();
    fireEvent.click(within(unsaved()[0]).getByRole("button", { name: /remove/i }));
    expect(screen.getByRole("heading", { name: "Images (1)" })).toBeInTheDocument();

    fireEvent.change(within(unsaved()[0]).getByLabelText(/evidence type/i), { target: { value: "Overall Vehicle Condition" } });
    fireEvent.click(within(unsaved()[0]).getByRole("button", { name: /retake/i }));
    expect(screen.getByRole("heading", { name: "Images (0)" })).toBeInTheDocument();
    await capture();
    expect(within(unsaved()[0]).getByLabelText(/evidence type/i)).toHaveValue("Overall Vehicle Condition");
  });

  it("will not save a photo without a usable location, and recovers after a retry", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    mockCamera();
    mockLocation({ code: 1 }, GOOD_FIX);
    renderPage();
    await openCamera();
    await capture();
    expect(within(unsaved()[0]).getByText(/location access is blocked/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save 1 image" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/usable location/i);
    expect(createEvidenceCapture).not.toHaveBeenCalled();

    await act(async () => fireEvent.click(within(unsaved()[0]).getByRole("button", { name: /retry location/i })));
    expect(within(unsaved()[0]).getByText(/location captured/i)).toBeInTheDocument();
  });

  it("flags a location that is not precise enough", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    mockCamera();
    mockLocation({ latitude: 13.08, longitude: 80.27, accuracy: 850 });
    renderPage();
    await openCamera();
    await capture();
    expect(within(unsaved()[0]).getByText(/±850 m - not precise enough/i)).toBeInTheDocument();
  });

  it("rejects an evidence date in the future or before the scheduled date", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    mockCamera();
    mockLocation(GOOD_FIX);
    renderPage();
    await openCamera();
    await capture();
    const dateInput = within(unsaved()[0]).getByLabelText(/evidence date/i);
    fireEvent.change(dateInput, { target: { value: "2099-01-01" } });
    expect(within(unsaved()[0]).getByText(/cannot be in the future/i)).toBeInTheDocument();
    fireEvent.change(dateInput, { target: { value: "2025-12-31" } });
    expect(within(unsaved()[0]).getByText(/before the scheduled inspection date/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save 1 image" }));
    expect(createEvidenceCapture).not.toHaveBeenCalled();
  });

  it("keeps a photo with the server's reason when its save fails", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    mockCamera();
    mockLocation(GOOD_FIX);
    createEvidenceCapture.mockRejectedValueOnce({ response: { status: 400, data: { detail: "The captured photo could not be read as an image." } } });
    renderPage();
    await openCamera();
    await capture();
    fireEvent.click(screen.getByRole("button", { name: "Save 1 image" }));
    expect(await within(unsaved()[0]).findByText("The captured photo could not be read as an image.")).toBeInTheDocument();
    expect(screen.queryByText(/photos? saved/i)).not.toBeInTheDocument();
    expect(nextButton()).toBeDisabled();
  });

  it("explains a blocked camera and never falls back to choosing a file", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    mockCamera({ failWith: "NotAllowedError" });
    const { container } = renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /open camera/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/camera access was blocked/i);
    expect(container.querySelector('input[type="file"]')).toBeNull();
  });

  it("explains when the browser has no camera support", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /open camera/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/cannot open the camera/i);
  });

  it("stops the camera when it is closed or the page is left", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail());
    mockCamera();
    mockLocation(GOOD_FIX);
    const { unmount } = renderPage();
    await openCamera();
    fireEvent.click(screen.getByRole("button", { name: /close camera/i }));
    expect(stopTrack).toHaveBeenCalledTimes(1);
    await openCamera();
    unmount();
    expect(stopTrack).toHaveBeenCalledTimes(2);
  });
});

describe("EvidencePage - saved evidence and step states", () => {
  it("shows the surveyor's saved photos as thumbnails with honest statuses", async () => {
    getAssignedClaimDetail.mockResolvedValue(completed());
    renderPage();
    expect(await screen.findByRole("heading", { name: "Images (1)" })).toBeInTheDocument();
    const tile = screen.getByRole("listitem", { name: /saved image/i });
    expect(within(tile).getByText("Counts as surveyor photo")).toBeInTheDocument();
    expect(within(tile).getByText(/13\.082700, 80\.270700/)).toBeInTheDocument();
    expect(within(tile).getByText("Not analysed yet")).toBeInTheDocument();
    await waitFor(() => expect(within(tile).getByRole("img")).toHaveAttribute("src", expect.stringMatching(/^blob:/)));
    expect(nextButton()).toBeEnabled();
  });

  it("is locked until the earlier steps are complete", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail({ wf: workflow("inspection") }));
    renderPage();
    expect(await screen.findByRole("heading", { name: "Complete the earlier steps first" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open camera/i })).not.toBeInTheDocument();
    expect(nextButton()).toBeDisabled();
  });

  it("is locked before the scheduled date", async () => {
    getAssignedClaimDetail.mockResolvedValue(detail({ wf: workflow("damage", { schedule: schedule({ reached: false }) }) }));
    renderPage();
    expect(await screen.findByRole("heading", { name: "Inspection not open yet" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open camera/i })).not.toBeInTheDocument();
  });

  it("is read-only once the survey report has been submitted", async () => {
    getAssignedClaimDetail.mockResolvedValue({ ...completed(), workflow: { ...workflow("submitted"), schedule: schedule() } });
    renderPage();
    expect(await screen.findByText(/can no longer be changed/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open camera/i })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Images (1)" })).toBeInTheDocument();
    fireEvent.click(nextButton());
    expect(await screen.findByText("Survey Report step")).toBeInTheDocument();
  });

  it("flags an older submission without surveyor photos instead of presenting it as verified", async () => {
    const review = {
      meets_current_requirements: false,
      problems: ["No photo captured with the in-app camera by the assigned surveyor, with a usable location reading, has been saved."],
      message: "This report was submitted, but its saved records do not meet the current submission requirements. It is kept exactly as submitted and has not been re-verified.",
    };
    getAssignedClaimDetail.mockResolvedValue(
      detail({ wf: { ...workflow("submitted", { qualifying_photo_count: 0, evidence_complete: false }), submission_review: review } })
    );
    renderPage();
    expect(await screen.findByRole("note")).toHaveTextContent(/do not meet the current submission requirements/i);
    expect(screen.getByRole("note")).toHaveTextContent(/in-app camera/i);
    expect(screen.getByRole("heading", { name: "Images (0)" })).toBeInTheDocument();
    expect(screen.getByText("No surveyor-captured images are recorded for this inspection.")).toBeInTheDocument();
    expect(screen.queryByText(/photos you capture appear here/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open camera|correct this step/i })).not.toBeInTheDocument();
  });

  it("shows no review notice when the submission meets the current rules", async () => {
    getAssignedClaimDetail.mockResolvedValue({
      ...completed(),
      workflow: { ...workflow("submitted"), submission_review: { meets_current_requirements: true, problems: [], message: "Submitted." } },
    });
    renderPage();
    expect(await screen.findByRole("heading", { name: "Images (1)" })).toBeInTheDocument();
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });
});
