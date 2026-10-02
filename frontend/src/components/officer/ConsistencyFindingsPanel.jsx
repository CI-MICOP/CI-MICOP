import { FileSearch, Info, ScanText } from "lucide-react";
import { useState } from "react";

import Button from "../common/Button";
import Card from "../common/Card";
import StatusBadge from "../common/StatusBadge";
import { analyzeClaimDocuments, checkClaimConsistency } from "../../services/officerService";
import { getApiErrorMessage } from "../../utils/errors";

// Explicit per-state tones - the generic getStatusTone() heuristic would
// render MATCH as neutral and MISMATCH as danger. A disagreement is shown
// as "needs review" (warning), never as an accusation (danger), and
// UNAVAILABLE/INCONCLUSIVE stay neutral so they never read as negative
// evidence.
const FINDING_TONE = {
  MATCH: "success",
  CONSISTENT: "success",
  MISMATCH: "warning",
  CONTRADICTION: "warning",
  UNAVAILABLE: "neutral",
  INCONCLUSIVE: "neutral",
};

const FINDING_LABEL = {
  MATCH: "Match",
  MISMATCH: "Mismatch",
  UNAVAILABLE: "Unavailable",
  CONSISTENT: "Consistent",
  CONTRADICTION: "Contradiction",
  INCONCLUSIVE: "Inconclusive",
};

const EXTRACTION_LABEL = {
  extracted_native: "Text extracted",
  extracted_ocr: "Text extracted (OCR)",
  extracted_ocr_no_confidence: "Text extracted (OCR, no confidence)",
  empty: "No text found",
  unavailable: "Extraction unavailable",
};

function FindingBadge({ status }) {
  return <StatusBadge label={FINDING_LABEL[status] ?? status} tone={FINDING_TONE[status] ?? "neutral"} />;
}

/**
 * Officer-side view of the Step 5.8.12/5.8.13-B/5.8.13-C document analysis
 * endpoints. Two explicit, separate actions:
 *   1. "Analyze Documents" - POST .../documents/analyze (OCR; persists only
 *      each document's own analysis fields).
 *   2. "Check Consistency" - POST .../documents/semantic-consistency
 *      (read-only; reads the already-extracted text).
 * The deterministic identifier result and the narrative prototype result
 * are rendered as two separate sections and are never merged into one
 * verdict or score. Nothing here calls the decision workflow.
 */
export default function ConsistencyFindingsPanel({ claimId }) {
  const [analysis, setAnalysis] = useState({ status: "idle", result: null, message: "" });
  const [check, setCheck] = useState({ status: "idle", result: null, message: "" });

  async function handleAnalyze() {
    setAnalysis({ status: "running", result: null, message: "" });
    try {
      const result = await analyzeClaimDocuments(claimId);
      setAnalysis({ status: "done", result, message: "" });
      // Extracted text may have changed, so any earlier findings are stale.
      setCheck({ status: "idle", result: null, message: "" });
    } catch (err) {
      setAnalysis({ status: "error", result: null, message: getApiErrorMessage(err) });
    }
  }

  async function handleCheck() {
    setCheck({ status: "running", result: null, message: "" });
    try {
      const result = await checkClaimConsistency(claimId);
      setCheck({ status: "done", result, message: "" });
    } catch (err) {
      setCheck({ status: "error", result: null, message: getApiErrorMessage(err) });
    }
  }

  const isBusy = analysis.status === "running" || check.status === "running";

  return (
    <Card className="mb-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">Live Document Consistency</h3>
          <p className="mt-1 text-sm text-muted">
            Computed from this claim's uploaded documents. Analyze the documents first, then check consistency.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="secondary" onClick={handleAnalyze} isLoading={analysis.status === "running"} disabled={isBusy}>
            <ScanText className="h-4 w-4" aria-hidden="true" />
            Analyze Documents
          </Button>
          <Button onClick={handleCheck} isLoading={check.status === "running"} disabled={isBusy}>
            <FileSearch className="h-4 w-4" aria-hidden="true" />
            Check Consistency
          </Button>
        </div>
      </div>

      <p className="mt-4 flex items-center gap-2 rounded-card border border-brand-200 bg-brand-50 p-3 text-sm text-brand-800">
        <Info className="h-4 w-4 shrink-0" aria-hidden="true" />
        Investigative findings for officer review only. A mismatch or contradiction is not an accusation of
        wrongdoing. Final claim decision remains with the Claims Officer.
      </p>

      {analysis.status === "error" && (
        <p className="mt-4 text-sm text-danger">Document analysis failed: {analysis.message}</p>
      )}
      {analysis.result && <AnalysisSummary result={analysis.result} />}

      {check.status === "error" && (
        <p className="mt-4 text-sm text-danger">Consistency check failed: {check.message}</p>
      )}
      {check.result && (
        <div className="mt-4 grid grid-cols-1 gap-4 border-t border-border pt-4 lg:grid-cols-2">
          <IdentifierSection deterministic={check.result.deterministic} />
          <NarrativeSection narrative={check.result.narrative} />
        </div>
      )}
    </Card>
  );
}

function AnalysisSummary({ result }) {
  const { completeness } = result;
  return (
    <div className="mt-4 space-y-3 border-t border-border pt-4 text-sm">
      <p className="text-ink">
        <span className="font-medium">{result.documents_analyzed}</span> document(s) analyzed.{" "}
        {completeness.explanation}
      </p>
      {completeness.missing_document_types.length > 0 && (
        <p className="text-muted">Missing: {completeness.missing_document_types.join(", ")}</p>
      )}
      {result.documents.length > 0 && (
        <ul className="space-y-1">
          {result.documents.map((doc) => (
            <li key={doc.Document_ID}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-ink">
                  {doc.Document_Type} <span className="text-muted">({doc.Document_ID})</span>
                </span>
                <StatusBadge
                  label={EXTRACTION_LABEL[doc.extraction_status] ?? doc.extraction_status}
                  tone={doc.extraction_status.startsWith("extracted") ? "success" : "neutral"}
                />
              </div>
              {doc.limitations.length > 0 && (
                <p className="mt-0.5 text-xs text-muted">{doc.limitations.join(" ")}</p>
              )}
            </li>
          ))}
        </ul>
      )}
      <p className="text-muted">Run "Check Consistency" to see findings based on the extracted text.</p>
    </div>
  );
}

const IDENTIFIERS = [
  ["registration", "Registration Number"],
  ["policy", "Policy Number"],
];

function IdentifierSection({ deterministic }) {
  return (
    <section aria-label="Identifier checks">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Identifier Checks</p>
      <ul className="space-y-3">
        {IDENTIFIERS.map(([key, label]) => {
          const finding = deterministic[key];
          return (
            <li key={key} className="rounded-card border border-border p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium text-ink">{label}</span>
                <FindingBadge status={finding.status} />
              </div>
              <dl className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                <Detail label="On Record" value={finding.structured_value ?? "—"} />
                <Detail label="Found in Document" value={finding.extracted_value ?? "—"} />
              </dl>
              {finding.matched_document_id && (
                <p className="mt-2 text-xs text-muted">
                  Source: {finding.matched_document_type} ({finding.matched_document_id})
                </p>
              )}
              <p className="mt-2 text-ink">{finding.explanation}</p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function NarrativeSection({ narrative }) {
  return (
    <section aria-label="Narrative check">
      <div className="mb-2 flex items-center gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted">Narrative Check</p>
        <StatusBadge label="Research Prototype" tone="info" />
      </div>
      <div className="rounded-card border border-border p-3 text-sm">
        <div className="flex items-center justify-between gap-3">
          <span className="font-medium text-ink">Accident Location: FIR vs. Survey Report</span>
          <FindingBadge status={narrative.relationship} />
        </div>
        <dl className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
          <Detail label="FIR" value={narrative.document_a?.document_id ?? "Not available"} />
          <Detail label="Survey Report" value={narrative.document_b?.document_id ?? "Not available"} />
        </dl>
        <p className="mt-2 text-ink">{narrative.explanation}</p>
        {narrative.limitations.length > 0 && (
          <div className="mt-3">
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Limitations</p>
            <ul className="list-disc space-y-1 pl-5 text-muted">
              {narrative.limitations.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="break-all text-ink">{value}</dd>
    </div>
  );
}
