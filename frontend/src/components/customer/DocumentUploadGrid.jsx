import { CheckCircle2, Info, Upload } from "lucide-react";

import AccidentPhotoCapture from "./AccidentPhotoCapture";
import { DOCUMENT_CATEGORIES, DOCUMENT_GROUPS, UPLOAD_ACCEPT } from "./documentCategories";

/**
 * Lets the customer pick files locally for each document category before
 * the claim exists. Selecting a file here only updates local state -
 * NewClaimPage uploads the selected files to POST /documents once the
 * claim has actually been created (a claim must exist before a document
 * can be linked to it). Categories are shown in three groups: the RC,
 * licence and policy copies required with every claim, accident photos
 * (camera only - see AccidentPhotoCapture), and other claim evidence.
 * `files.accident_photos` is a list; every other key holds one File.
 */
export default function DocumentUploadGrid({ files, onFileChange, disabled = false }) {
  return (
    <div className="space-y-6">
      <p className="flex gap-2 rounded-card border border-border bg-surface p-3 text-xs text-muted">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" aria-hidden="true" />
        Uploading a document doesn't mean it has been verified - a claims officer reviews every claim, and you may be
        asked for a clearer copy.
      </p>
      {DOCUMENT_GROUPS.map((group) => (
        <section key={group.key}>
          <h3 className="text-sm font-semibold text-ink">{group.title}</h3>
          <p className="mb-3 mt-0.5 text-xs text-muted">{group.description}</p>
          {group.key === "photos" ? (
            <AccidentPhotoCapture
              photos={files.accident_photos ?? []}
              onChange={(photos) => onFileChange("accident_photos", photos.length ? photos : null)}
              disabled={disabled}
            />
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {DOCUMENT_CATEGORIES.filter((category) => category.group === group.key && category.input === "file").map(
                (category) => {
                  const file = files[category.key];
                  return (
                    <label
                      key={category.key}
                      className="flex cursor-pointer flex-col gap-2 rounded-card border border-dashed border-border bg-surface p-4 text-sm hover:border-brand-400"
                    >
                      <span className="flex items-center gap-2 font-medium text-ink">
                        {file ? (
                          <CheckCircle2 className="h-4 w-4 text-success" aria-hidden="true" />
                        ) : (
                          <Upload className="h-4 w-4 text-muted" aria-hidden="true" />
                        )}
                        {category.label}
                      </span>
                      <span className="truncate text-xs text-muted">{file ? file.name : "Click to select a file"}</span>
                      <input
                        type="file"
                        accept={UPLOAD_ACCEPT}
                        className="sr-only"
                        disabled={disabled}
                        onChange={(event) => onFileChange(category.key, event.target.files?.[0] ?? null)}
                      />
                    </label>
                  );
                }
              )}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
