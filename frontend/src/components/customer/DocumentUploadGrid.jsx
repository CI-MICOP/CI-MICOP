import { CheckCircle2, Upload } from "lucide-react";

import { DOCUMENT_CATEGORIES } from "./documentCategories";

/**
 * Lets the customer pick files locally for each document category. There
 * is no document-upload endpoint on the backend yet (only GET /documents),
 * so nothing here is actually sent anywhere - selecting a file only
 * updates local state. See the Step 4.3 report for the missing-API note.
 */
export default function DocumentUploadGrid({ files, onFileChange }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {DOCUMENT_CATEGORIES.map((category) => {
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
              className="sr-only"
              onChange={(event) => onFileChange(category.key, event.target.files?.[0] ?? null)}
            />
          </label>
        );
      })}
    </div>
  );
}
