# MVP delivery plan — published breakdown

Drafted 2026-11-16 from the owner's issue #38 walkthrough and subsequent discussion. The owner requested development and its metrics first, checkpoint evaluation and its metrics second, and final evaluation third; each milestone must end with verification that its delivered workflow works.

The owner approved the revised issue breakdown on 2026-11-16; it was published as three milestones and issues #40–#48. This delivery plan is not a new scientific specification or execution approval. The [approved baseline specification](../BASELINE_PILOT_SPEC.md) remains authoritative. Current work status belongs in GitHub Issues. Preserve the owner's existing walkthrough edits and evidence. The owner's subsequent clarification requires real behavior in every delivery slice; the [published issue breakdown](MVP_ISSUE_DRAFTS.md) implements that requirement. The [publication record](MVP_GITHUB_ISSUES.json) maps every slice to its verified GitHub issue and milestone.

## Planning structure

Use the baseline specification and this delivery plan as common context for three GitHub milestones and their implementation issues. A separate umbrella PRD is optional, not a prerequisite to publishing the reviewed slices with `/to-issues`. Three separate scientific specifications or another layer of epics are unnecessary. A focused engineering contract can be written when a milestone needs one; it must reference the common rules rather than duplicate them.

Deliver Document Portal first: one real checkpoint, then three incremental checkpoints, then the ten-step sequence. This is an implementation order within the five-application baseline scope, not a reduction of that scope. Read the existing issues before publishing follow-ups; extend or reference their work rather than reproducing the original backlog.

Each milestone ends with an acceptance record: versions, exact commands, expected/observed behavior, evidence paths, passes, failures, skips and blockers. A milestone acceptance check verifies the platform. The experiment's final deep security assessment investigates the generated application; these are different activities.

## Shared operator experience

Proposed command shape, subject to implementation refinement:

```text
principiis init --application document-portal --run portal-demo
principiis develop --run portal-demo --step 1
principiis status --run portal-demo
principiis preview --run portal-demo --step 1
principiis evaluate --run portal-demo --step 1
principiis assess-final --run portal-demo
principiis report --run portal-demo --format csv
```

These commands do not exist in this form today. Prefer one small entry point composing the existing controller over a second execution engine. Initialization resolves reusable local configuration; subsequent commands should not require hand-built argv JSON, repeated path plumbing, or manually authored hash lists. Versioned evaluator bundles should supply their dependency manifests.

Every action prints a clear status and the locations of the application snapshot, logs and reports. Reports are saved as artifacts, with readable output and JSON/CSV exports. Preview runs a disposable copy in a restricted environment and prints its local URL and cleanup command; it does not edit the retained snapshot.

Development, checkpoint evaluation and final assessment remain separately triggered. No automatic next step, retry, or repair. A failed candidate is a recorded outcome; an infrastructure/evaluator failure is separately identified. Shell status conventions must be explicit so the operator can distinguish a recorded candidate failure from command failure.

Every delivery issue requires evidence from real generated application artifacts or real execution, appropriate to its behavior. Fake executors, canned scores and simulated assessor responses are regression-test aids, never sufficient completion evidence. Live launches must fall within explicit recorded authorization; fixture evidence cannot substitute when a required live check is blocked. Preserve unsuccessful applications and do not rerun completed development to obtain a favorable result. Milestone acceptance checks can reuse compatible retained real evidence without repeating model calls.

## Milestone 1 — develop, preview and measure

**Outcome:** The owner can select a portal request, invoke ordinary Codex, inspect the resulting application and read trustworthy development metrics through a few commands.

Build on the existing Codex adapter, manual development, snapshots, retry journal and resource accounting. Deliver a reusable configuration/preflight path, an execution environment that prevents developer access to the research checkout/future requests/evaluators/results, prepared toolchains and a restricted application preview. Keep normal development tools and network access available.

Development qualification must be possible before portal scoring is ready. The current controller requires evaluator commands and fingerprints their contents during development; resolve this coupling explicitly for engineering rehearsals rather than supplying dummy portal checks. Retain exact request/runtime provenance and make evaluator readiness visible. A development-only rehearsal is not a qualified baseline experiment. Before any comparison run, freeze the task/check contracts as required by the baseline spec.

| Slice | Type | Depends on | Independently verifiable result |
| --- | --- | --- | --- |
| D1. Build and preview portal request 1 with actual Codex | HITL | None | Reviewed runtime and simple command produce real application source, a preserved snapshot, restricted preview and measured development evidence; no evaluator or next request starts. |
| D2. Develop portal requests 2–3 with fresh sessions and retained code | AFK | D1 | Actual Codex sessions extend the previous source and preserve notes, incremental request visibility and per-step metrics. |
| D3. Recover an interrupted real run and reconcile development exports | HITL | D1, D2 | A separate authorized interruption/retry rehearsal preserves partial evidence and restores the last completed snapshot. JSON/CSV/readable reports reconcile all real attempts; the owner completes milestone-1 acceptance. |

Development metrics: run/application/condition/request versions, checkpoint/attempt/session IDs, snapshot identity, UTC start/end, active elapsed time, execution status, reported input/output/cache/reasoning tokens, sampled peak local process-group RSS with its measurement scope, and requested/effective model/reasoning plus harness version. Keep raw measurement references. Unknown values remain unknown. Cache/reasoning subsets are not extra tokens; retries remain in totals; idle operator time is distinct from active execution. Actual subscription spending and hosted-model RAM remain unknown.

**Acceptance:** Complete the real portal development/preview and interruption/recovery cases above, verify isolation, and reconcile exported metrics against their retained live evidence. Deterministic regression tests additionally cover malformed configuration and misleading candidate-owned artifacts. A broken generated app is permissible experimental output, but its launch failure must be distinguishable from a broken platform. If a working preview cannot be demonstrated, record that limitation and keep acceptance incomplete. Do not require hidden security scoring for this milestone.

## Milestone 2 — independently evaluate every checkpoint and measure it

**Outcome:** One explicit command evaluates a selected preserved checkpoint against its applicable functional/security contract, without regenerating or repairing code. Results and evaluation resources appear separately in the same run report.

Complete the current portal evaluator binding and runtime preparation. Qualify checkpoints 1–3 first, then extend qualification through all ten requests. Browser and direct backend checks must cover applicable requirements and regressions, including explicitly modeled retained-data upgrades where required. Fix checkpoint copying/integrity inconsistencies before trusting evaluation evidence. Generate and verify complete dependency manifests from versioned evaluator artifacts; qualification must establish that the declared runtime/dependency set is usable.

| Slice | Type | Depends on | Independently verifiable result |
| --- | --- | --- | --- |
| E1. Evaluate the generated portal at checkpoint 1 | AFK | D3; existing #8 | Real browser/backend checks execute against the actual generated snapshot and produce evidence-backed primary scores/resources through the simple entry point. |
| E2. Evaluate generated checkpoints 2–3 and retain evaluation reruns | AFK | E1 | Actual browser/backend regression and data-continuation checks assess the matching snapshots; primary/rerun evidence and metrics remain separate. |
| E3. Demonstrate ten real development/evaluation checkpoints | HITL | E2; existing #9 | A frozen ten-step package supports separately triggered real Codex development and actual evaluation at every checkpoint; ten-checkpoint reports and milestone-2 acceptance reconcile the retained evidence. |

Checkpoint evaluation metrics: functional/security pass, fail or unassessable; joint outcome; applicable/passed/failed/unassessable check counts where supported; evaluator errors; evaluator/version/dependency/image identities; assessed snapshot identity; attempt/primary/rerun role; elapsed time; exposed tokens if an agent is invoked; scoped local memory; logs and reproducible browser/backend evidence. Deterministic tests use no model, so model tokens are unavailable/not applicable, not fabricated. Keep development and evaluation totals separate.

**Acceptance:** Assess the actual generated portal at all ten checkpoints and retain browser/backend evidence for the resulting scores, including any failures. Separately demonstrate joint pass, functional failure, security-property failure and evaluator/runtime error with genuine executable controls, and repeat controls to expose flakiness. Verify rerun retention, snapshot integrity, requirement changes, regression coverage and report/resource reconciliation. Qualify all ten checkpoints before declaring this milestone complete. Retained milestone-1 snapshots may support diagnostic checks; do not retrospectively label them a qualified baseline experiment. If request/check/runtime bindings have changed, use a fresh frozen development run rather than mutating an old run's fingerprint.

## Milestone 3 — final deep assessment and complete workflow verification

**Outcome:** After checkpoint 10, a separately triggered assessment investigates additional vulnerabilities in the final application and produces evidence-backed findings with its own resource record.

Build on the existing independent-investigation stage. Select one supported assessor initially: ordinary subscription Codex is the existing default. DeepSec is a candidate requiring suitability, execution-mode, licensing and cost review before adoption; this proposal makes no claim that it is supported. Do not introduce a generic assessor plugin framework. Freeze the final assessment prompt/configuration, tools and verification procedure before comparison runs.

| Slice | Type | Depends on | Independently verifiable result |
| --- | --- | --- | --- |
| F1. Run a real final security assessment on checkpoint 10 | HITL | E3 | Agree/freeze the assessor contract and actually invoke the assessor on the final generated application, retaining genuine output, assessment status, snapshot provenance and metrics. |
| F2. Reproduce final-assessment findings and export their status | AFK | F1 | Run reviewed evidence procedures against disposable copies of the real application, retain verified/rejected/unresolved adjudication, and export actual assessment resources and evidence links. No minimum vulnerability count is required. |
| F3. Complete the real MVP acceptance walkthrough and report | HITL | D3, E3, F2 | The owner exercises the delivered commands and inspects the real app, ten primary assessments, final investigation and reconciled JSON/CSV/readable reports. Compatible retained evidence avoids needless model reruns. |

Final assessment metrics: status, assessed snapshot, assessor/model/settings/tools/prompt versions, elapsed time, reported tokens and scoped memory, claims with verified/rejected/unresolved status, operator-adjudicated root-cause deduplication, and evidence/reproduction references. Severity may be reported with a stated rubric and uncertainty. Findings remain supplementary; raw finding counts are not security ground truth. Verification/adjudication effort and unknown resource fields remain visible. Avoid adding an investigation's inclusive elapsed time to its component agent/tool times again.

**Acceptance:** Execute the real assessor on the final generated portal and investigate its actual claims. Separately use executable controls to exercise verification, rejection, unresolved findings, assessor failure and snapshot-tampering rejection; controls must be labeled and never counted as candidate findings. Verify final assessment neither edits original source/scores nor sends findings to development. The complete authorized rehearsal must yield local JSON/CSV/readable reports with source/preview references, all attempts/errors, primary-score history and separate development/checkpoint/final-assessment accounting. Compare summaries to source evidence. No discovered vulnerability is required for completion. Record partial completion honestly if runtime or candidate problems prevent exercising a path.

## Existing work and dependencies

| Existing issue | Relationship to this proposal |
| --- | --- |
| [#38](https://github.com/SrFlipFlop/principiis-obsta/issues/38) | Source of operator UX findings and retained fixture evidence; not a prerequisite to repeat the entire manual checklist. |
| [#3](https://github.com/SrFlipFlop/principiis-obsta/issues/3), [#4](https://github.com/SrFlipFlop/principiis-obsta/issues/4), [#5](https://github.com/SrFlipFlop/principiis-obsta/issues/5) — closed | Reuse Codex execution, accounting and recovery; create focused follow-ups for integration/defects instead of rebuilding them. |
| [#6](https://github.com/SrFlipFlop/principiis-obsta/issues/6), [#7](https://github.com/SrFlipFlop/principiis-obsta/issues/7) — closed | Reuse restricted evaluation and independent investigation; fixture completion does not qualify the revised portal workflow. |
| [#8](https://github.com/SrFlipFlop/principiis-obsta/issues/8), [#9](https://github.com/SrFlipFlop/principiis-obsta/issues/9) — open | Existing authoring/qualification work supplies the executable packages consumed by E1/E3; preserve request versions and approval history. New slices prove integration with generated applications rather than duplicate this authoring. |
| [#18](https://github.com/SrFlipFlop/principiis-obsta/issues/18) — open | Reporting implementation exists; reconcile remaining acceptance/integration work with D2, E2 and F2. |
| [#19](https://github.com/SrFlipFlop/principiis-obsta/issues/19) — open | Full five-application readiness/launch remains beyond a portal-only demonstration. Already selected execution settings need no renewed decision. |

The [architecture review](../reviews/ARCHITECTURE_REVIEW.md) records follow-up findings relevant here: trusted resource-artifact discovery, validation before attempt allocation, snapshot integrity in investigation, consistent symlink/copy semantics and bounded memory-sampler storage. Reproduce the relevant findings against the current code and fix them in the slice that depends on their behavior. This plan does not claim to have requalified those paths.

## Execution and scope boundaries

- Preserve the selected subscription/default-model/default-reasoning setup, no model-stage time limits, and at most three explicit additional development retries. Effective settings remain unknown when unexposed.
- Each development request starts a fresh session with prior source/agent notes and cumulative requirements; evaluation findings and future requests remain inaccessible. Candidate failures do not earn development retries.
- Technical preparation and deterministic verification can proceed within approved implementation scope. Live subscription rehearsals require explicit launch authorization; this planning request starts no model runs. Paid APIs remain unauthorized.
- Preserve/version requests, evaluator changes, manifests and historical artifacts. No reference implementation enters developer context; no live hidden result becomes a new benchmark bug report.
- No dashboard, infrastructure deployment, later intervention, automatic repair, extra model/harness comparison or efficacy claim is part of this MVP delivery work.

## Publication

The owner reviewed and approved the three milestones, slice granularity, dependencies and HITL/AFK assignments in the [issue breakdown](MVP_ISSUE_DRAFTS.md). Three milestones and nine follow-up issues were published in dependency order; no new umbrella issue was needed. Existing issues remain unchanged. The AFK label describes implementation ownership, not permission to start an unapproved live run; each required live acceptance check must have recorded launch authorization.
