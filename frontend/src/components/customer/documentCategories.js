// Keys map to the backend's ALLOWED_DOCUMENT_TYPES (services/document_upload.py).
// The order is the upload order - keep it stable. `group` only affects how the
// upload grid presents the categories. `input` is "file" (choose a file) or
// "camera" (taken with the portal camera - there is no file picker for it).
// Every type's file is stored (services/document_upload.py); driving_licence,
// rc_book and insurance_policy additionally reduce what is saved into
// Extracted_Text to just the verification record, never the full OCR text
// (backend/app/services/claim_copy_retention.py) - the stored file itself is
// the full, unredacted copy, viewable by an assigned surveyor.
export const DOCUMENT_CATEGORIES = [
  { key: "fir_copy", label: "FIR Copy", group: "evidence", input: "file" },
  { key: "driving_licence", label: "Driving Licence", group: "claim_copy", input: "file" },
  { key: "rc_book", label: "RC Book", group: "claim_copy", input: "file" },
  { key: "insurance_policy", label: "Insurance Policy", group: "claim_copy", input: "file" },
  { key: "repair_estimate", label: "Repair Estimate", group: "evidence", input: "file" },
  { key: "accident_photos", label: "Accident Photos", group: "photos", input: "camera" },
];

// Copies required with every claim, whatever the claim type.
export const REQUIRED_COPY_KEYS = ["driving_licence", "rc_book", "insurance_policy"];

export const MAX_ACCIDENT_PHOTOS = 10;

// Mirrors DOCUMENT_MAX_UPLOAD_BYTES in backend/app/core/config.py.
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

export const UPLOAD_ACCEPT = ".pdf,.jpg,.jpeg,.png";

export const DOCUMENT_GROUPS = [
  {
    key: "claim_copy",
    title: "Required with every claim",
    description:
      "Upload a copy of the driving licence of whoever was driving, the vehicle's RC and your insurance policy - even if your insurer already holds these on record, because the copy is checked against those records. Each copy is read for the check and is not kept: only the details needed for checking (such as the registration or policy number) are saved with your claim.",
  },
  {
    key: "photos",
    title: "Accident photos",
    description:
      "Take photos of the vehicle damage and the scene with your device's camera. Photos can't be chosen from your gallery or files. Please don't take photos of yourself here - they should show the vehicle and the scene.",
  },
  {
    key: "evidence",
    title: "Other claim evidence",
    description:
      "The police FIR if the police were involved, and the garage's repair estimate if the vehicle is being repaired. These are kept with your claim.",
  },
];

/**
 * Flattens the selected files into one upload item per file, in category
 * order: { id, category, label, file }. Accident photos are a list, so each
 * photo becomes its own item.
 */
export function selectedUploadItems(files) {
  return DOCUMENT_CATEGORIES.flatMap((category) => {
    const value = files[category.key];
    if (!value) return [];
    if (Array.isArray(value)) {
      return value.map((file, index) => ({
        id: `${category.key}-${index + 1}`,
        category,
        label: `${category.label} ${index + 1}`,
        file,
      }));
    }
    return [{ id: category.key, category, label: category.label, file: value }];
  });
}

export function missingRequiredCopies(files) {
  return DOCUMENT_CATEGORIES.filter((c) => REQUIRED_COPY_KEYS.includes(c.key) && !files[c.key]);
}
