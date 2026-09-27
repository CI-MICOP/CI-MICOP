# Deterministic Cross-Document Consistency (Step 5.8.13-B)

## 1. Purpose

Step 5.8.13-A built a deterministic entity-extraction foundation that
answers *"what entities can be found in this document's text?"* but
explicitly never compared that text against anything else. Step 5.8.13-B
closes that one specific gap: it compares an already-extracted entity
candidate against the claim's own structured reference value and reports
a deterministic **MATCH / MISMATCH / UNAVAILABLE** verdict.

This is **deterministic consistency checking, not fraud detection.** A
`MISMATCH` is reported only as an inconsistency signal - a fact about two
pieces of data disagreeing - never as an accusation, a probability, or a
claim outcome.

## 2. Supported Comparisons

1. **Vehicle registration number** - extracted candidate vs.
   `vehicles.Registration_Number` (via `claims.Vehicle_ID`).
2. **Policy number** - extracted candidate vs. `policies.Policy_Number`
   (via `claims.Policy_ID`).

No other comparison exists. Cross-document *narrative* consistency (e.g.
comparing damage descriptions between a surveyor report and a repair
estimate) is out of scope - it would require NLI/semantic similarity,
which remains deliberately unbuilt (Section 9).

## 3. Normalization

`services/document_consistency.py` reuses `entity_extraction.py`'s own
normalization functions verbatim - `normalize_registration` and
`normalize_policy`, both promoted from module-private to public in this
step specifically so this reuse is possible without a second,
possibly-diverging implementation:

- **Registration:** uppercased, internal spaces and hyphens removed -
  `"TN 38 AB 1234"`, `"TN-38-AB-1234"`, and `"tn38ab1234"` all normalize to
  `"TN38AB1234"`.
- **Policy:** uppercased, internal whitespace collapsed to one space, but
  hyphens are preserved (part of this project's own `POL-XXXXXX`
  convention) - `"POL-000042"` and `"pol-000042"` normalize to the same
  value; `"POL-000042"` and `"POL 000042"` do **not** (a hyphen and a
  space are different separators under this existing rule, unchanged from
  Step 5.8.13-A).

## 4. Document-Type Rules

Comparison is restricted to exactly one document type per entity - **RC**
for registration numbers, **Insurance Policy** for policy numbers - the
project's own live upload vocabulary
(`services/document_upload.py::ALLOWED_DOCUMENT_TYPES`). This is narrower
than Step 5.8.13-A's extraction step (which still scans every document
type, just without a confidence boost): the Step 5.8.13 audit found no
evidence that any other document type is a reliable source for either
entity, so no other type is considered here. A claim with no document of
the relevant type is reported `UNAVAILABLE`, never treated as a mismatch.

## 5. Candidate-Resolution Rule

All candidates of the target entity type are gathered across every
relevant document on the claim (re-reading each document's
**already-persisted** `Extracted_Text` - this module never re-runs OCR).
They are deduplicated by normalized value, then resolved deterministically:

1. **Exactly one distinct value** (the common case - one candidate, or
   several documents/candidates that all agree): compared directly against
   the normalized structured reference → `MATCH` or `MISMATCH`.
2. **Multiple disagreeing distinct values, and the reference is among
   them:** → `MATCH` - the correct value was found among the noise. The
   explanation notes that other, non-matching candidates also existed.
3. **Multiple disagreeing distinct values, reference not among them, and
   every candidate is format-verified** (`source == "regex_strict_format"`,
   i.e. no candidate came only from the weaker keyword-context fallback):
   → `MISMATCH` - the evidence is "sufficiently explicit": several
   independently well-formed values were found, and none is the insured
   record.
4. **Multiple disagreeing distinct values, reference not among them, and
   at least one candidate is only a weak keyword-context guess (unverified
   shape):** → `UNAVAILABLE` - the disagreement is not explicit enough to
   justify a confident mismatch claim.

No probability or ranking is computed anywhere in this rule - only a
candidate's categorical `source` (strict-format vs. keyword-context, both
already produced deterministically by Step 5.8.13-A) is used to decide
between rules 3 and 4.

## 6. MATCH / MISMATCH / UNAVAILABLE Semantics

- **MATCH:** a usable extracted entity exists and equals the structured
  reference after normalization.
- **MISMATCH:** a usable extracted entity exists and does not equal the
  structured reference (per the explicit-evidence rule above).
- **UNAVAILABLE:** there is insufficient evidence to compare - no relevant
  document, no extracted text, no usable candidate, no structured
  reference, or ambiguous disagreeing evidence that isn't explicit enough
  to call a mismatch.

## 7. Why UNAVAILABLE Is Not MISMATCH

Treating "no evidence" the same as "evidence of a problem" would be
dishonest and, in an insurance-claims context, actively harmful - a claim
with a not-yet-uploaded RC document is not evidence of anything wrong with
that claim. `UNAVAILABLE` and `MISMATCH` are kept as distinct, separately
reported states everywhere in this module (schema, service, tests) so a
consumer can never conflate "we don't know" with "these don't match."

## 8. The `cross_document_consistency` Table Was Left Untouched

The Step 5.8.13 audit found this table lacks explanation text, document
provenance (which document(s) were compared), and timestamps - and this
step's result needs exactly that provenance (`matched_document_type`,
`matched_document_id`) to be honest and explainable. Rather than force a
richer result into a schema that can't represent it (silently losing which
document produced a verdict, or overwriting a per-claim row with no audit
trail), **no migration was created and the table was not touched.** The
comparison is computed at read time and returned directly in the API
response - exactly the same choice Step 5.8.12 made for document
completeness before it, and the same "read-time result when persistence
isn't cleanly supported" pattern established across this project's prior
AI-adjacent steps.

## 9. Why NLI/Embeddings Are Deferred

No NLI, sentence-embedding, or transformer-based infrastructure exists
anywhere in this repository (confirmed by the Step 5.8.13 audit). This
step's comparisons are exact-value, deterministic identifier matching -
nothing here requires or would benefit from semantic similarity. Building
NLI now, with no real live document corpus to validate it against, would
risk presenting an unvalidated capability as if it worked. It remains
explicitly out of scope, to be considered only after this deterministic
foundation has been reviewed and, ideally, validated against real
documents at scale.

## 10. API Integration

No new endpoint was created. Both existing analyze endpoints gained one
additional `consistency` field:

- `POST /api/v1/documents/{document_id}/analyze` - `consistency` reflects
  the whole claim's current documents (computed the same way regardless of
  which single document was just analyzed).
- `POST /api/v1/officer/claims/{claim_id}/documents/analyze` - `consistency`
  appears both at the top level and, identically, inside each per-document
  entry (mirroring how `completeness` already worked).

RBAC is completely unchanged - both endpoints still resolve the claim and
document server-side via the existing `get_claim_or_403`/`require_roles`
dependencies; no new access-control logic was introduced, and no
client-supplied path or arbitrary document list is ever accepted.

## 11. Response Shape

```json
{
  "registration": {
    "status": "MATCH",
    "structured_value": "TN01AB0001",
    "extracted_value": "TN01AB0001",
    "matched_document_type": "RC",
    "matched_document_id": "DOC-20260927-EC5A47",
    "explanation": "Registration number extracted from RC matches the insured record."
  },
  "policy": {
    "status": "UNAVAILABLE",
    "structured_value": "DEV-POLICY-001",
    "extracted_value": null,
    "matched_document_type": null,
    "matched_document_id": null,
    "explanation": "Policy number could not be compared because no Insurance Policy document exists for this claim."
  }
}
```

No filesystem path, Tesseract configuration, storage location, or
credential ever appears in this response - it exposes only the structured
reference value, the extracted candidate, the verdict, and its
explanation.

## 12. Security / RBAC

Unchanged from Step 5.8.12/5.8.13-A: document/claim access is resolved
server-side via existing dependencies before any comparison runs; a
customer can never trigger a comparison against another customer's
document (confirmed by a dedicated 403 test); Officer/Admin-only access to
the claim-level endpoint is unchanged (confirmed by a dedicated test).

## 13. Limitations

- Comparison quality is entirely dependent on Step 5.8.12's OCR/extraction
  quality and Step 5.8.13-A's regex-based candidate detection - neither
  has been validated against a representative corpus of real uploaded
  insurance documents.
- Restricted to exactly two entities and exactly one "reliable" document
  type each - no other identifier or document type is compared.
- The multi-candidate resolution rule (Section 5) is a documented,
  reasoned design choice, not an empirically validated one - it has not
  been tuned or tested against real disagreeing-candidate scenarios beyond
  the controlled test cases in this step's test suite.
- No explanation or verdict is persisted - every call recomputes the
  result fresh from current data, so there is no historical record of a
  past comparison.

## 14. Controlled Validation

Manually validated against the real development claim `DEV-CLM-001`
(`vehicles.Registration_Number = "TN01AB0001"`,
`policies.Policy_Number = "DEV-POLICY-001"`), using genuine PyMuPDF-built
PDFs uploaded and analyzed through the real API, one at a time with
cleanup between each so claims were compared in isolation:

- **Case A** (RC document containing `TN01AB0001`) → `MATCH`.
- **Case B** (RC document containing `KA05MH1234`) → `MISMATCH`.
- **Case C** (only an FIR document, no RC) → `UNAVAILABLE`.
- **Policy** (Insurance Policy document containing `DEV-POLICY-001`) →
  `MATCH`.

These are **controlled test documents**, not the project's offline
synthetic dataset (whose document text is Faker-generated filler
unrelated to any real claim fact) and not a claim that this reflects
real-world OCR accuracy - see Step 5.8.12/5.8.13-A's own documentation for
that distinction, which still applies unchanged here.

## 15. Future Integration Point

This comparison result is **not** wired into `ai_pipeline.py` as a risk
signal in this step - fusion weights, the uncertainty formula, signal
count, and confidence aggregation are all unchanged. A future step may
consume `compare_claim_documents()`'s result as a new signal family once
this deterministic foundation has been reviewed and, ideally, validated
against real uploaded documents at scale - mirroring exactly how
`document_completeness` was integrated only after Step 5.8.12 was reviewed
and accepted.
