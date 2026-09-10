# AI/ML Validation Findings (Step 5.3)

**Validation-study disclaimer:** This experiment is a validation study using the currently available CI-MICOP dataset. The dataset is synthetic/de-identified and therefore the measured performance must not be interpreted as production fraud-detection, risk-scoring, or consistency-checking accuracy. Real-world validation requires appropriately governed insurer claims data.

This report synthesizes [AI_ML_DATASET_AUDIT.md](AI_ML_DATASET_AUDIT.md) (Step 5.1), [AI_VS_NON_AI_RESULTS.md](AI_VS_NON_AI_RESULTS.md) (Step 5.2), and [SECONDARY_TARGET_RESULTS.md](SECONDARY_TARGET_RESULTS.md) (Step 5.3) into a single, honest answer to the questions that matter for deciding what CI-MICOP's AI/ML work should become.

---

### 1. Which targets contain useful signal?

**None of the four targets tested across Step 5.2/5.3 show a reliable, leakage-safe predictive signal** once evaluated against an appropriate chance baseline with repeated grouped validation:

- `frd_Fraud_Label`: best PR-AUC 0.167-0.233 depending on model and split, but the Random Forest/Logistic Regression ordering itself is not stable under repeated CV (Section 13 of SECONDARY_TARGET_RESULTS.md) - the entire 0.16-0.19 PR-AUC band all four approaches (2 ML, 2 rule baselines) converge to under CV is only modestly above the 15.1% base rate.
- `est_Excessive_Claim_Amount_Indicator`: rule baseline and both ML models land at or within noise of the 46.9% base rate (chance).
- `frd_Risk_Category`: ROC-AUC (OVR macro) 0.50-0.51 - indistinguishable from chance for a 4-class problem.
- `cdc_Overall_Consistency_Status`: ROC-AUC (OVR macro) 0.51-0.54, and neither model beats "always predict the majority class."

The honest, useful finding of Step 5.2+5.3 combined is not "which target works" but that **the currently available synthetic dataset does not contain a target with strong, leakage-free predictive signal** - see Question 8.

### 2. Which targets are weak?

All four, ranked from "least weak" to "not reliable at all":
1. `frd_Fraud_Label` - weak but real: models beat the rule baseline on PR-AUC in the single Step 5.2 split, though not consistently under CV.
2. `est_Excessive_Claim_Amount_Indicator` - at chance for both the rule baseline and both ML models.
3. `cdc_Overall_Consistency_Status` - marginally above chance ROC-AUC but neither model beats the majority-class accuracy baseline.
4. `frd_Risk_Category` - fully at chance (ROC-AUC ~0.50).

### 3. Which targets have leakage concerns?

Every target required active leakage control, and two produced leakage findings a naive "exclude the target's own table" rule would have missed entirely:
- **`frd_Risk_Category`**: `frd_Fraud_Label` is DEFINITE leakage even though it lives outside Risk_Category's own source table - Risk_Category = Low/Medium implies Fraud_Label = 0 with 100% consistency in this dataset (Section 11, SECONDARY_TARGET_RESULTS.md). A model given access to Fraud_Label would trivially "solve" two of the four classes without learning anything generalizable.
- **`est_Excessive_Claim_Amount_Indicator`**: `frd_Excessive_Claim_Amount_Indicator` is a cross-table duplicate of the same concept and was excluded even though it agrees with the real target only 53.8% of the time (not a literal copy, but the same concept re-asserted).
- **`cdc_Overall_Consistency_Status`**: no cross-table leak found, but every other column in its own table was kept excluded as POTENTIAL_LEAKAGE (same generation process) even after verifying none of them actually determines the target - caution was kept even where the empirical risk turned out to be low.
- **`frd_Fraud_Label`** (Step 5.2, restated here for completeness): the entire `fraud_risk_analysis`, `claim_decision_audit`, and `tp_claims` tables are excluded as leakage, per the original Step 5.1 audit.

### 4. Which model is most stable?

**Logistic Regression**, by a modest but consistent margin. Across every target tested with repeated CV, Logistic Regression's metric standard deviation was equal to or smaller than Random Forest's (e.g. fraud PR-AUC std 0.036 vs 0.039; Risk_Category macro-F1 std 0.022 vs 0.034; Excessive-Amount F1 std 0.028 vs 0.029). Random Forest's higher variance is consistent with it being the higher-capacity model on a comparatively small dataset (654 claims) with many one-hot-expanded categorical features.

### 5. Does Random Forest consistently outperform Logistic Regression?

**No.** In the single Step 5.2 train/test split, Random Forest had the highest fraud PR-AUC (0.233 vs Logistic Regression's 0.222). Under 5-fold x 3-seed repeated grouped CV (Step 5.3, Section 13), that ordering **reverses**: Logistic Regression's mean PR-AUC (0.189) is higher than Random Forest's (0.177), and the gap (0.012) is smaller than the combined variability of both (std 0.033). For the secondary targets, the two models are statistically indistinguishable on every headline metric. **The Step 5.2 conclusion that "Random Forest performs best" does not survive robustness testing and should not be treated as a settled result.**

### 6. Does AI consistently outperform the rule baseline?

**No, and the comparison is closer than Step 5.2's single split suggested.** Under repeated CV, both rule baselines (v1: PR-AUC 0.156; v2: PR-AUC 0.156 - identical because v2 only changes the decision threshold, not the underlying score ranking) sit only slightly behind both ML models (LR 0.189, RF 0.177) for fraud, and the ML models never had a stable, reproducible lead. For `est_Excessive_Claim_Amount_Indicator`, the rule baseline (PR-AUC 0.472) is essentially tied with both ML models (0.458-0.470) - all three are at chance. For `Risk_Category` and `Consistency_Status`, **no defensible rule baseline could even be constructed** (Section 7, SECONDARY_TARGET_RESULTS.md) - there is no AI-vs-non-AI comparison to make for those two targets at all.

### 7. Does the result change under grouped repeated validation?

**Yes, substantially, and this is the most important methodological finding of Step 5.3.** A single customer-grouped train/test split (Step 5.2's approach) is not enough to draw a stable conclusion from ~654 claims: the Random Forest/Logistic Regression ranking for fraud reversed once evaluated across 15 grouped fold-runs instead of 1. Any future claim that "model X is best" on this dataset should be treated as provisional until confirmed under repeated grouped CV.

### 8. What does the dataset limitation mean?

The recurring pattern across Step 5.1, 5.2, and 5.3 is the same: **several of CI-MICOP's labels (`Fraud_Label`, `Risk_Category`, `Overall_Consistency_Status`, `Excessive_Claim_Amount_Indicator`) do not appear to be deterministic functions of their own visible, same-table component signals** (Section 2, SECONDARY_TARGET_RESULTS.md - e.g. `Overall_Consistency_Status` has zero relationship with the count of individual field-level mismatches that would normally explain it). This is consistent with these labels being generated independently (e.g. randomly, or from a process not represented anywhere in the exported tables) rather than derived from the claim's own recorded facts. The practical implication: **no amount of additional feature engineering or model tuning on this exact dataset export is likely to substantially improve these results**, because the signal these targets would need appears not to be present in the data, not merely hard to extract. A genuinely predictive model requires either (a) a differently-generated / real-world dataset where labels are actually derived from recorded claim facts, or (b) access to whatever generation logic produced these labels, which is not present in the current export.

### 9. Which AI module should become the strongest CI-MICOP research contribution?

Not the fraud/risk/consistency prediction models themselves - their honestly-reported near-chance performance is a valid research finding, but not a strong *system* contribution. The strongest, most defensible research contribution from this project is the **methodology layer that stayed constant across every target tested**:

- A leakage-control architecture (`feature_builder.py` + the Step 5.3 target-specific refinement layer) that classifies every candidate feature as SAFE / POTENTIAL_LEAKAGE / DEFINITE_LEAKAGE per target, catches cross-table duplicate-concept leaks that naive prefix rules miss, and is verified against the real data rather than assumed.
- A Customer_ID-grouped, repeated cross-validation protocol that demonstrably changes conclusions (Question 7) - i.e. it is not decorative rigor, it materially affects what can be claimed.
- An explainability + human-readable reason-code layer that is explicit about the difference between "screening signal" and "confirmed cause," and that was validated to generalize to a target (`Excessive_Claim_Amount_Indicator`) beyond the one it was originally built for.
- The explicit, non-AI rule-baseline-vs-ML comparison framework, including the discipline to state plainly when *no* defensible non-AI baseline exists (`Risk_Category`, `Consistency_Status`) rather than inventing one.

**Recommendation:** position CI-MICOP's research contribution as a rigorous, leakage-aware validation methodology for insurer claims AI/ML on a constrained synthetic dataset - honestly reporting that the currently available labels do not support strong predictive claims - rather than as a fraud-detection or risk-scoring system with strong measured accuracy, which the data does not support.

---

## Recommended Step 5.4

Given the findings above, Step 5.4 should **not** attempt further tuning of these same four targets against this same dataset export (Section 8 - it would not be expected to help). Instead:
1. Package the leakage-control + grouped-repeated-CV + explainability methodology as a documented, reusable validation framework (the actual research contribution - Question 9).
2. If a differently-sourced or larger claims dataset becomes available, re-run this exact pipeline against it as the real test of whether the methodology (not this specific data) generalizes.
3. Any officer-facing UI work should surface Rule Baseline v2 and the repeated-CV-confirmed uncertainty (not the single-split "Random Forest wins" framing) so the Claims Officer sees the same honestly-caveated picture this report does.
