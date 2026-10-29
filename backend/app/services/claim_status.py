"""This project's own Claim_Status vocabulary.

claims.Claim_Status has no DB-level enum (it is a free String(30) column),
and the original approved dataset's own Claim_Status values are not loaded
into this database (see docs/project_documentation/AI_ML_DATASET_AUDIT.md -
that vocabulary echoes Final_Decision and is flagged as leakage-adjacent,
not a live workflow value). The two values below are this project's actual,
deliberately small status vocabulary: a claim starts "Under Review"
(services/claim_creation.py) and becomes "Completed" once an officer
records any final decision for it - Approved, Rejected, or Partially
Approved alike (services/claim_decision.py). Claim_Status tracks lifecycle
stage only (is this claim still awaiting a decision, or has the officer
finished processing it); the differentiated outcome itself lives in
Final_Decision, never in Claim_Status.
"""

UNDER_REVIEW_STATUS = "Under Review"
COMPLETED_STATUS = "Completed"
