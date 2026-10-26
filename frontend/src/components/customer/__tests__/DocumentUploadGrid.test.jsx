import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import DocumentUploadGrid from "../DocumentUploadGrid";
import { DOCUMENT_CATEGORIES, DOCUMENT_GROUPS, missingRequiredCopies, selectedUploadItems } from "../documentCategories";

function section(name) {
  return screen.getByRole("heading", { name }).closest("section");
}

describe("DocumentUploadGrid", () => {
  it("asks for RC, licence and policy uploads with every claim, without saying the insurer's copy is enough", () => {
    render(<DocumentUploadGrid files={{}} onFileChange={() => {}} />);
    const copies = section("Required with every claim");
    for (const label of ["Driving Licence", "RC Book", "Insurance Policy"]) {
      expect(within(copies).getByLabelText(new RegExp(label))).toHaveAttribute("type", "file");
    }
    expect(copies).toHaveTextContent(/even if your insurer already holds these/i);
    expect(copies).toHaveTextContent(/is not kept/i);
    expect(screen.queryByText(/insurer may already hold/i)).not.toBeInTheDocument();
  });

  it("offers accident photos through the camera only - no file input for them", () => {
    render(<DocumentUploadGrid files={{}} onFileChange={() => {}} />);
    const photos = section("Accident photos");
    expect(within(photos).getByRole("button", { name: /open camera/i })).toBeInTheDocument();
    expect(photos.querySelector('input[type="file"]')).toBeNull();
    expect(screen.queryByLabelText(/accident photos/i)).not.toBeInTheDocument();
    expect(photos).toHaveTextContent(/please don't take photos of yourself here/i);
  });

  it("keeps FIR, repair estimate and survey report as kept claim evidence uploads", () => {
    render(<DocumentUploadGrid files={{}} onFileChange={() => {}} />);
    const evidence = section("Other claim evidence");
    for (const label of ["FIR Copy", "Repair Estimate", "Survey Report"]) {
      expect(within(evidence).getByLabelText(new RegExp(label))).toHaveAttribute("type", "file");
    }
    expect(evidence).toHaveTextContent(/kept with your claim/i);
  });

  it("says that uploading is not verification", () => {
    render(<DocumentUploadGrid files={{}} onFileChange={() => {}} />);
    expect(screen.getByText(/doesn't mean it has been verified/i)).toBeInTheDocument();
  });

  it("still offers every existing category exactly once, in a known group", () => {
    const { container } = render(<DocumentUploadGrid files={{}} onFileChange={() => {}} />);
    const groups = new Set(DOCUMENT_GROUPS.map((group) => group.key));
    for (const category of DOCUMENT_CATEGORIES) {
      expect(groups.has(category.group)).toBe(true);
    }
    expect(container.querySelectorAll('input[type="file"]')).toHaveLength(6);
    expect(DOCUMENT_CATEGORIES.map((c) => c.key)).toEqual([
      "fir_copy", "driving_licence", "rc_book", "insurance_policy", "repair_estimate", "accident_photos", "survey_report",
    ]);
    expect(DOCUMENT_CATEGORIES.filter((c) => !c.retained).map((c) => c.key)).toEqual([
      "driving_licence", "rc_book", "insurance_policy",
    ]);
  });

  it("reports the chosen file under the category's backend key", () => {
    const onFileChange = vi.fn();
    render(<DocumentUploadGrid files={{}} onFileChange={onFileChange} />);
    const file = new File(["x"], "rc.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText(/RC Book/), { target: { files: [file] } });
    expect(onFileChange).toHaveBeenCalledWith("rc_book", file);
  });
});

describe("upload helpers", () => {
  it("turns each accident photo into its own upload item, in category order", () => {
    const rc = new File(["x"], "rc.pdf");
    const photos = [new File(["a"], "a.jpg"), new File(["b"], "b.jpg")];
    const items = selectedUploadItems({ accident_photos: photos, rc_book: rc });
    expect(items.map((item) => [item.id, item.category.key, item.file])).toEqual([
      ["rc_book", "rc_book", rc],
      ["accident_photos-1", "accident_photos", photos[0]],
      ["accident_photos-2", "accident_photos", photos[1]],
    ]);
  });

  it("lists the required copies that are still missing", () => {
    expect(missingRequiredCopies({ rc_book: new File(["x"], "rc.pdf") }).map((c) => c.key)).toEqual([
      "driving_licence", "insurance_policy",
    ]);
  });
});
