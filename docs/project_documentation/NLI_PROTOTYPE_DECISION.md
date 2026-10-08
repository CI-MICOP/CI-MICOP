# Decision: Research-Grade NLI Prototype (Step 5.8.19)

## 1. Objective

Roadmap item 7: "Decide whether a research-grade NLI prototype is justified."

NLI (natural language inference) is a type of language model that reads two
pieces of text and says whether the second one agrees with the first,
contradicts it, or neither. The project proposal named such a model
(DeBERTa NLI, with multilingual-e5 embeddings) for cross-document
consistency. The current system does not use one: it compares documents
with deterministic rules.

This step is a **decision only**. No code, dependency, schema, migration,
risk-fusion or decision-logic change was made.

## 2. Decision

**Deferred, not rejected. No NLI or embedding model is added in the current
phase.**

The NLI model stays in the project plan as future work. The project
timeline has a later phase, "Model Development, Validation & Expanded Data
Collection" (November 2026 - January 2027), and that is the right place for
it, because the main thing missing today is data to test it on (Section
4.1).

Until then, the rule-based checks are the project's cross-document
consistency method. Section 6 lists what has to be ready before the NLI
experiment starts.

## 3. What the System Does Today

| Check | Method | Result on its controlled corpus |
|---|---|---|
| Registration number, policy number | Pattern extraction, exact comparison | Step 5.8.13-B tests and manual run on DEV-CLM-001 |
| Accident date, FIR number | Labelled-field extraction | 22 / 25 agree, 0 false mismatches |
| Accident time | Labelled-field extraction, 30-minute tolerance | 10 / 11 agree, 0 false mismatches |
| FIR vs Survey Report location | Keyword + capitalised place name | 15 / 23 agree, 2 false contradictions |

Sources: `CONSISTENCY_IMPROVEMENTS.md`, `LIVE_SIGNAL_INTEGRATION.md`.

Only the location check reads free narrative text, so it is the only place
an NLI model could replace an existing rule.

## 4. Reasons for Not Doing It Now

### 4.1 There is no data to test an NLI model on

Judging a language model needs many example document pairs with a trusted
correct answer for each. The project has:

- 23 location pairs, hand-written by the team, deliberately weighted towards
  hard phrasings;
- no real FIR or survey report narratives;
- synthetic dataset documents whose text is unrelated filler
  (`SEMANTIC_CONSISTENCY_VALIDATION.md`, Section 3).

With 23 cases, one case changing is a swing of about 4 percentage points. A
model could not be shown to be better or worse than the rules, and any
figure reported for it would not be defensible.

### 4.2 The remaining errors are not the kind NLI is built for

All 8 location cases that still disagree with the ideal label were reviewed:

| Cases | Cause | What would address it |
|---|---|---|
| V10, V11 | Two names for one place ("Anna Salai" / "Anna Salai Junction", "Anna Salai" / "Mount Road") | A list of local place names and aliases |
| V13, V14 | Place not picked up ("T. Nagar", lower-case "anna salai") | Small extraction-rule changes |
| V09, V16, V18, V23 | Two places in one document (a city and a street, or a hospital) | A rule to prefer the most specific place |

None of these is a failure to understand a sentence. V10 and V11 need local
geographic knowledge; the rest are extraction details. This is an assessment
from reading the cases, **not a measured result** - no NLI model was run.

### 4.3 The cost is high for this project

- An NLI model needs PyTorch and the transformers library plus a model
  download of several hundred megabytes. `backend/requirements.txt` has
  neither today.
- The development laptop is already memory-limited: the frontend test suite
  has to run with one worker (`CONSISTENCY_IMPROVEMENTS.md`, Section 7).
- The project rule is "Do not add heavy ML dependencies without a justified
  research need."

### 4.4 It would weaken explainability

Each current result can be traced to the exact words that produced it
("near Anna Salai" vs "near Guindy"). An NLI model returns a label and a
score with no such trace. The project also has a rule not to invent
confidence probabilities; an NLI score would look like a probability
without being a calibrated one for this domain.

## 5. What Is Given Up

This decision has a real cost, recorded here so it is not overstated later:

- Consistency checking stays limited to **registration, policy, accident
  date, accident time, FIR number and location**.
- There is **no** check of fault, sequence of events, injuries or damage
  description across documents. These are the things an NLI model could, in
  principle, compare and rules cannot.
- The system must **not** be described as using NLI, embeddings or
  "semantic AI" today. The location check is a rule-based prototype. In
  presentations, NLI should be labelled as planned, not as built.

## 6. What Must Be Ready First

The NLI experiment is planned for the model-development phase (November
2026 - January 2027). Start it once all of these hold:

1. A labelled set of accident narrative pairs exists, at least a few hundred
   pairs, with labels written by someone other than the person building the
   model.
2. The pairs cover what rules cannot do (fault, sequence, injury, damage),
   not only location.
3. The experiment runs offline in `ai_ml/`, with its own requirements file,
   and is compared against the current rules on the same pairs.
4. Nothing is wired into the backend or risk fusion unless that comparison
   shows a clear, documented improvement.

## 7. Cheaper Next Improvements (not implemented)

If location results need to improve, these rule changes target the actual
remaining errors and need no new dependency:

- prefer the most specific place when a city and a street both appear
  (V09, V18, V23);
- ignore hospital and police-station names as accident locations (V16);
- accept abbreviated names such as "T. Nagar" (V13);
- a small, sourced alias list (V11), only if its scope is justified.

Each would need its own held-out cases, as in Step 5.8.17.

## 8. Limitations of This Decision

- It rests on a 23-case, hand-written corpus and on reasoning about what an
  NLI model would do. No NLI model was run or measured.
- Section 4.2 is the project team's assessment, not an experimental finding.
- The decision is about this project's current data and resources. It is not
  a claim that NLI is unsuitable for insurance documents in general.

## 9. Validation

Documentation only. No code was changed and the test suites were not re-run
for this step.
