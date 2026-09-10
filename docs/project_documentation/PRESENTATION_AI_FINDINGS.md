# Presentation: AI Findings (Step 5.7)

*Plain-language summary for a college project presentation. For full detail and every source number, see `FINAL_AI_VS_NON_AI_EVALUATION.md`.*

---

## A. Problem

Motor insurance claims processing today relies on manual document review, manual cross-checking, and manual surveyor assignment. This is slow to formalize, hard to audit, and doesn't systematically flag risk signals or balance surveyor workload.

## B. Traditional approach

A Claims Officer manually reads documents, compares them, applies simple rule-of-thumb fraud checks, reviews the repair estimate, prioritizes claims informally (e.g. first-come-first-served), and assigns surveyors to the nearest available person by hand.

## C. CI-MICOP AI approach

CI-MICOP extracts structured signals from the claim's documents, evidence, and repair estimate; combines several of these signals into one risk score; estimates how *confident* that score is (separately from how *risky* it is); explains which factors drove the result in plain language; recommends a review priority; and optionally recommends a surveyor assignment using Ant Colony Optimization. **The Claims Officer still makes every final decision** - nothing here approves, rejects, or auto-assigns anything.

## D. What was tested

Six research steps, all on the same 654-claim synthetic dataset:
1. Dataset/leakage audit
2. Rule baseline vs. Logistic Regression vs. Random Forest for fraud
3. Repeated cross-validation robustness check (5 targets)
4. Multi-signal risk fusion + uncertainty
5. Claims Officer UI integration (read-only prototype)
6. Ant Colony Optimization vs. greedy surveyor assignment

## E. What improved

- A repeatable, code-defined analytical pipeline that runs the same way every time (no manual variability).
- Every signal comes with a plain-language explanation and a reason code - not a black box.
- An explicit confidence/uncertainty score, kept separate from the risk score, so "high risk but not sure" is a real, distinct state.
- A structured review-priority recommendation instead of ad hoc triage.
- A transparent, inspectable surveyor-assignment cost function (distance + workload + priority), instead of an unstated, undocumented manual process.

## F. What did not improve

- Fraud prediction: the AI models were only marginally different from a simple rule baseline, and that small difference was not stable when tested repeatedly (PR-AUC ~0.16-0.19 across all approaches).
- Predicting risk category, document-consistency status, and excessive-claim-amount: all landed at roughly chance level - no better than guessing based on the class proportions.
- Combining multiple signals together (risk fusion) did not beat the single best signal by a statistically meaningful amount.
- The optimization algorithm (ACO) did not consistently beat a much simpler, much faster greedy assignment method.

## G. Why the negative findings matter

Reporting "it didn't work better" honestly, instead of hiding it, is itself a research result. These experiments demonstrate *why* rigorous methodology matters: without leakage control, grouped cross-validation, and repeated testing, it would have been easy to wrongly conclude "Random Forest is the best fraud model" (Step 5.2's single-split result) - a conclusion that did not survive repeated testing (Step 5.3). The same discipline applied to risk fusion and ACO. This is the difference between a project that reports whatever number looks best and one that reports what is actually true.

## H. Research contribution

CI-MICOP proposes an integrated motor insurance claims decision-support architecture that combines leakage-aware AI analysis, multi-signal risk fusion, uncertainty estimation, explainable reasoning, and optimization-assisted surveyor assignment - while keeping a human Claims Officer in charge of every final decision. This is not claimed to be the first, unique, or state-of-the-art system - the contribution is the integrated, transparent, honestly-evaluated architecture.

## I. Limitations

- The dataset is synthetic/de-identified, not real insurer data.
- Several target labels behave like independently-generated values rather than being predictable from the claim's own recorded facts.
- Surveyor locations, workloads, and availability used in the optimization experiment are entirely synthetic.
- No real-world financial savings, processing-time reduction, or officer-decision-quality improvement was measured.

## J. Future work

Real-world validation would need: real (governed, de-identified) insurer claims data, genuinely verified fraud outcomes, measured document-processing and human-review times, real repair-estimate outcomes, real surveyor travel/time and workload data, and a direct comparison against an insurer's actual existing workflow.

---

## 30-second explanation

"We built an AI-assisted claims analysis system for motor insurance and tested it honestly against simple non-AI baselines. On our synthetic dataset, the AI didn't prove it's more accurate - the differences were within normal statistical noise, and two of the four prediction targets were basically at chance level. What we did build and validate is the architecture: automatic signal extraction, multi-signal fusion, an uncertainty score that's kept separate from the risk score, plain-language explanations, and an optimization-assisted surveyor assignment option - all while the human Claims Officer keeps the final decision. The contribution is the integrated, transparent, honestly-tested system, not a claim of higher accuracy."

## 2-minute panel explanation

"Our research question was whether an AI-assisted claims workflow does better than a conventional one. We tested this across six steps. First, we audited the dataset for leakage and label quality. Then we compared a transparent rule-based fraud screen against Logistic Regression and Random Forest - on a single train/test split, Random Forest looked best, but when we repeated the test five-fold across three random seeds with customer-grouped validation, that result reversed, and all three approaches landed in the same narrow performance band. We found the same pattern for three other targets - risk category, document consistency, and excessive-claim-amount - all came out close to chance level, and two of them scored worse than just always guessing the most common class. We then tried combining multiple risk signals together instead of using just one, and added an explicit uncertainty estimate that's deliberately kept separate from the risk score, so the system can say 'this looks risky, but I'm not confident' rather than collapsing everything into one number. That combination didn't beat the single best signal by a statistically meaningful margin either. Finally, we tested Ant Colony Optimization against a simple greedy method for assigning surveyors to claims, on a clearly-labeled synthetic scenario since our dataset doesn't contain real surveyor location or workload data - ACO didn't consistently win there either, and was about a thousand times slower. So our honest answer is: this project does not prove AI is more accurate than a simple baseline on this dataset. What it does demonstrate is a complete, transparent, auditable decision-support architecture - automated signals, fusion, uncertainty, explainability, and optimization - that assists a human Claims Officer without ever making the decision for them. We think that disciplined, honest evaluation - including reporting the negative results - is itself the more valuable outcome than an inflated accuracy number would have been."
