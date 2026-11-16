# MVP issue breakdown — real behavior in every slice

Prepared, owner-approved and published on 2026-11-16. Source: [delivery plan](MVP_DELIVERY_PLAN.md), the [approved baseline specification](../BASELINE_PILOT_SPEC.md), and the owner's explicit requirement that every slice deliver real development/evaluation rather than fixture-only demonstrations. This file preserves the reviewed issue bodies; GitHub holds current work status.

Published three GitHub milestones and nine issues in dependency order. Local identifiers D1–F3 remain as planning aliases here; published bodies use actual issue numbers. There is no published parent PRD. Existing #8 and #9 are genuine external dependencies, not new work to duplicate. Existing #18/#19/#38 remain unchanged. Issue bodies, labels, milestone assignments and open states were verified after publication; details are in the [publication record](MVP_GITHUB_ISSUES.json).

| Milestone | Published issues |
| --- | --- |
| [MVP 1 — Development](https://github.com/SrFlipFlop/principiis-obsta/milestone/1) | D1: [#40](https://github.com/SrFlipFlop/principiis-obsta/issues/40), D2: [#41](https://github.com/SrFlipFlop/principiis-obsta/issues/41), D3: [#42](https://github.com/SrFlipFlop/principiis-obsta/issues/42) |
| [MVP 2 — Checkpoint evaluation](https://github.com/SrFlipFlop/principiis-obsta/milestone/2) | E1: [#43](https://github.com/SrFlipFlop/principiis-obsta/issues/43), E2: [#44](https://github.com/SrFlipFlop/principiis-obsta/issues/44), E3: [#45](https://github.com/SrFlipFlop/principiis-obsta/issues/45) |
| [MVP 3 — Final assessment](https://github.com/SrFlipFlop/principiis-obsta/milestone/3) | F1: [#46](https://github.com/SrFlipFlop/principiis-obsta/issues/46), F2: [#47](https://github.com/SrFlipFlop/principiis-obsta/issues/47), F3: [#48](https://github.com/SrFlipFlop/principiis-obsta/issues/48) |

## Shared completion requirements

The following paragraph was included in each published issue's What to build section:

> Completion requires exercising the delivered behavior with real Codex-generated application artifacts, real execution and retained evidence as applicable. Fixtures and simulated model responses can support regression tests but cannot satisfy live acceptance. Preserve failures and unknown metrics; never substitute canned scores or an author-provided application for the generated candidate. Live execution requires recorded authorization covering its scope; do not launch from this issue alone, use paid APIs, or feed evaluation results back to development. AFK/HITL describes implementation ownership and does not override launch authorization.

Use the existing subscription/default model/default reasoning settings, no model-stage time limits and at most three explicit additional development retries. Preserve prior code/agent notes in fresh sessions; future requests, researcher instructions and hidden evaluation artifacts must be inaccessible to development. Perform meaningful behavioral tests and independent review for changes. Keep raw hidden materials and credentials out of public issues.

## Published milestones and acceptance gates

1. **MVP 1 — Real development, preview and development metrics.** Close only after D1–D3 demonstrate actual portal development, incremental continuation, interruption/recovery and reconciled exports. No primary security score is required here.
2. **MVP 2 — Real checkpoint evaluation and evaluation metrics.** Close only after E1–E3 assess ten actual generated checkpoints with qualified browser/backend checks and reconcile scores, reruns, errors and resources.
3. **MVP 3 — Real final security assessment and complete MVP acceptance.** Close only after F1–F3 exercise an actual assessor on the final application, verify evidence handling and demonstrate the complete operator workflow and reports.

## 1. D1 — Build and preview portal request 1 with actual Codex

Milestone: MVP 1. Type: HITL. Label: `ready-for-human`.

### What to build

Provide the first complete real-development path: initialize reusable local run configuration, select portal request 1, invoke ordinary subscription Codex in a reviewed isolated runtime, preserve its source and expose a restricted browser preview. Print understandable execution status, artifact locations and development measurements. Prepare the runtime and toolchain as part of delivering this path; an argv wrapper that only runs the greeting fixture is insufficient. Human work covers runtime/access review and a scoped live launch decision, not renewed approval of already selected model/retry settings.

Development rehearsals must be possible before hidden portal checks are qualified. Expose that readiness honestly and remove the dependency on dummy evaluator commands. Keep development provenance fixed; later evaluator binding must be explicit and versioned. This does not qualify a baseline experiment.

### Acceptance criteria

- [ ] A documented command sequence using reusable configuration invokes actual subscription Codex from an empty project with the real released portal request 1.
- [ ] Reviewed runtime boundaries prevent access to the research checkout, future requests, hidden checks and results while preserving ordinary development tools/network access. Validate malformed configuration before allocating an attempt.
- [ ] The retained output contains actual application source, request/version identity, snapshot/hash, session/settings/harness evidence, exit status and genuine logs; no evaluation or next development step starts automatically.
- [ ] A disposable restricted preview of the generated application provides a local URL and cleanup procedure. Demonstrate a reachable portal and record browser/backend startup evidence. A generated failure remains preserved; do not rerun completed development just to obtain a working app.
- [ ] Development elapsed time, reported token categories and scoped sampled local memory are saved in structured evidence and a readable summary, with unavailable fields explicitly unknown.
- [ ] The issue records the authorized live run's versions, commands, source/preview evidence and observed result. If no working preview can be demonstrated, record the limitation and leave acceptance incomplete.

### Blocked by

None — implementation can start immediately. Required live acceptance waits for a reviewed runtime and explicit scoped launch authorization.

## 2. D2 — Develop portal requests 2–3 with fresh sessions and retained code

Milestone: MVP 1. Type: AFK. Label: `ready-for-agent`.

### What to build

Extend the simple development command to the next selected request of the real portal run. Actual Codex sessions evolve the previous generated source while the operator retains control of advancement. Show real per-checkpoint progress, source and preview references and resource evidence. This is incremental development, not authoring a reference portal or replaying recorded responses.

### Acceptance criteria

- [ ] Separately triggered actual Codex sessions process requests 2 and 3 in order using the prior completed source and agent-authored notes; session identities are fresh and prior conversation/external memory is absent.
- [ ] Each session receives cumulative requirements through its selected request; later requests and all evaluator artifacts/results remain inaccessible.
- [ ] Each resulting checkpoint retains its own source, snapshot identity, request/settings provenance, logs, status and actual resource measurements; earlier checkpoints remain intact.
- [ ] Preview the retained outputs and record the observed collection/member and search/archive/export behavior, including missing or broken behavior without repairing the candidate outside the run. Milestone-1 acceptance requires a demonstrated usable preview path, not that every requested feature passes hidden tests.
- [ ] Missing prior checkpoints, out-of-order selection and completed-checkpoint replay are rejected clearly; candidate failures remain valid starting points for the next requested development step.
- [ ] The operator can locate real source, active development time, tokens and scoped memory for each checkpoint from status/report output without manually opening multiple JSON records.

### Blocked by

- D1.

## 3. D3 — Recover an interrupted real run and reconcile development exports

Milestone: MVP 1. Type: HITL. Label: `ready-for-human`.

### What to build

Complete development recovery and reporting using real attempts. In a separately identified authorized qualification run, interrupt actual Codex development and explicitly retry from the last completed checkpoint. Deliver saved JSON/CSV/readable reports covering the real successful, incomplete and retried attempts. Finish milestone 1 with an operator acceptance walkthrough; retain the earlier D1–D2 evidence.

### Acceptance criteria

- [ ] A planned interruption during actual Codex execution retains partial workspace, logs, known usage and interruption status; an explicit retry restores the last completed snapshot rather than carrying partial edits into the new attempt.
- [ ] Original attempt evidence survives and the retry has a distinct attempt/session identity. Retry count/eligibility rules are enforced with meaningful behavioral regression tests.
- [ ] Saved JSON, CSV and readable reports reconcile the D1–D2 run and the separately identified recovery run to their individual evidence; runs are never pooled as one sequence or double-counted.
- [ ] Reports identify active development time versus wall time including idle gaps, input/output token totals with cache/reasoning subsets, scoped memory and unknown spending/hosted memory. Candidate-owned files cannot enter controller accounting.
- [ ] Status explains where to find the actual app, logs and next permissible action. Changed configuration produces a clear new-run requirement rather than rewriting history.
- [ ] Owner acceptance verifies real development, preview, continuation, interruption/retry and exports, preserving pass/failure/skip/blocker evidence. Smoke-test success alone cannot close milestone 1.

### Blocked by

- D1.
- D2.

## 4. E1 — Evaluate the generated portal at checkpoint 1

Milestone: MVP 2. Type: AFK. Label: `ready-for-agent`.

### What to build

Expose one explicit evaluation command that uses the qualified portal package from existing issue #8 to execute genuine browser and direct backend checks against the generated checkpoint-1 snapshot. Integrate the real evaluator binding, candidate dependency preparation, restricted runtime and complete dependency provenance. Reuse existing evaluation machinery; this issue delivers integration with the generated candidate rather than duplicating #8's authoring work.

### Acceptance criteria

- [ ] Real hidden browser/backend checks execute against a disposable restricted copy of an actual Codex-generated checkpoint-1 portal; no model development or repair occurs during evaluation.
- [ ] The bound request/check versions, complete dependency manifest, runtime/image identities and assessed snapshot identity are verified and retained; no guessed manifest or historical incompatible bundle is accepted.
- [ ] Functional/security outcomes and joint status derive from actual executed checks with evidence references. Missing/unassessable checks and evaluator/runtime failures never become passes or arbitrary candidate failures.
- [ ] Genuine browser/backend traces/logs and separate evaluation elapsed time, scoped resource measurements and any exposed model usage are retained. Deterministic check execution does not invent model tokens.
- [ ] Snapshot validation/copying supports the documented file semantics and rejects tampering; original application bytes and development result stay unchanged. Changed evaluator binding never silently rewrites a retained development fingerprint.
- [ ] Status and saved JSON/CSV/readable reports join the real primary assessment to its development checkpoint. Qualified executable controls separately establish correct scoring; they are labeled controls, not candidate results.

### Blocked by

- D3.
- Existing #8 — qualified and bound portal evaluator package for requests 1–3.

## 5. E2 — Evaluate generated checkpoints 2–3 and retain reruns

Milestone: MVP 2. Type: AFK. Label: `ready-for-agent`.

### What to build

Evaluate the actual portal snapshots after requests 2 and 3 with the matching cumulative requirements, changed policies and regression checks. Support explicit evaluation-only reruns with separate provenance and measurements. Exercise the actual browser/backend and retained-data behavior rather than inferring it from preserved source files.

### Acceptance criteria

- [ ] Matching qualified browser/backend checks actually assess generated checkpoints 2 and 3, including earlier applicable requirements and new collection/search/archive/export behavior.
- [ ] Where the contract requires data survival across upgrades, a versioned continuation fixture exercises actual prior database contents and the new application version; source preservation alone is not treated as migration evidence.
- [ ] One explicit rerun of a real retained checkpoint appends assessment/log/resource evidence while preserving the first primary assessment and all snapshot bytes; development is not invoked again.
- [ ] Qualified executable controls demonstrate regression detection, legitimate requirement supersession, candidate failure and evaluator failure. Candidate outcomes remain those actually observed, with no obligation to produce a passing score.
- [ ] Reports and CSV/JSON exports reconcile all real primary/rerun assessments, version identities, failures and separate development/evaluation measurements without duplication.

### Blocked by

- E1.

## 6. E3 — Demonstrate ten real development/evaluation checkpoints

Milestone: MVP 2. Type: HITL. Label: `ready-for-human`.

### What to build

Use the qualified ten-step portal package supplied by existing #9 to demonstrate the real manual development/evaluation sequence through checkpoint 10 and close milestone 2. Freeze request/check/runtime contracts before the qualification run. Reuse compatible retained evidence; if extending or rebinding the package changes a frozen run's configuration, preserve that run and start a new identified run from an empty project.

### Acceptance criteria

- [ ] Ten actual Codex development sessions/checkpoints and ten separately triggered primary browser/backend assessments are retained under a consistent frozen run configuration; no fake executor or canned score supplies a checkpoint.
- [ ] At each step, only permitted requirements/source/notes reach development, evaluation stays hidden, and no next step or repair starts automatically.
- [ ] Actual successes, candidate failures, unassessable results and infrastructure/evaluator errors are accurately represented. A failing candidate does not authorize a development retry or erase the remaining sequence history.
- [ ] Reports expose requirement/check coverage and checkpoint provenance across all ten steps, with the applicable regression/supersession mappings supplied by #9.
- [ ] Saved JSON/CSV/readable reports reconcile per-step and aggregate development/evaluation resources, attempts, primary assessments and reruns against genuine retained evidence.
- [ ] Owner milestone-2 acceptance records commands, versions, real browser/backend evidence and remaining limitations. No model reliability or intervention-efficacy conclusion is inferred from this rehearsal.

### Blocked by

- E2.
- Existing #9 — qualified ten-step portal request/evaluator package.

## 7. F1 — Run a real final security assessment on checkpoint 10

Milestone: MVP 3. Type: HITL. Label: `ready-for-human`.

### What to build

Deliver a final-assessment command that actually invokes an independent assessor on the final generated portal. Agree and freeze scope, prompt, permitted tools, evidence procedure and execution configuration before the live assessment. Start with the supported ordinary subscription Codex path unless the owner selects another qualified tool. DeepSec is a candidate, not an existing supported integration or authorization for paid execution. Contract drafting alone does not complete this issue.

### Acceptance criteria

- [ ] Reviewed configuration identifies the actual assessor, requested/effective model/settings when exposed, scope, prompt/tools versions and authorized execution mode.
- [ ] The command validates and identifies the real checkpoint-10 snapshot, then invokes the real assessor on a disposable copy with final requirements and permitted materials; canned responses cannot satisfy this check.
- [ ] Source inspection and any dynamic application/browser probes respect the evaluation boundary; generated application code is never executed unrestricted on the controller host.
- [ ] Genuine assessor output, exit/error status, elapsed time, reported usage, scoped memory and snapshot/configuration provenance are retained and visible through status/report output.
- [ ] No developer is invoked, no final assessment findings reach development, and primary scores/retained application bytes remain unchanged. A failed assessment stays a failed attempt; an empty successful assessment is distinct and valid.
- [ ] The actual assessment attempt and its evidence are retained even if tool/environment limitations prevent successful completion; unresolved blockers keep acceptance open.

### Blocked by

- E3.

## 8. F2 — Reproduce final-assessment findings and export their status

Milestone: MVP 3. Type: AFK. Label: `ready-for-agent`.

### What to build

Take the real assessor output from F1 through reviewed reproducible verification and adjudication, then export evidence-linked verified/rejected/unresolved findings and final-assessment resources. Reuse the independent-investigation machinery while correcting any integrity/accounting gaps needed by this path. Report the outcome honestly even if the assessor finds no vulnerabilities.

### Acceptance criteria

- [ ] Actual assessor claims are retained and linked to reviewed reproduction procedures on disposable copies of the assessed application; neither agent self-assertion nor exit zero alone verifies a vulnerability.
- [ ] Verified claims include reproducible evidence and scope; rejected and unresolved claims retain their reasons/evidence. Root-cause deduplication preserves individual observations without inflating findings.
- [ ] If the real assessor returns no claims, report that result and scope accurately; do not inject vulnerabilities or fabricate a minimum finding count. Separately labeled executable controls exercise verification/rejection/unresolved paths.
- [ ] Saved JSON/CSV/readable exports link real assessment findings, evidence, snapshot identity and versions while preserving predefined checkpoint scores.
- [ ] Final-assessment resources are separate from development and primary evaluation; inclusive investigation time is not added again to its component durations. Reproduction/adjudication measurement gaps remain explicit.
- [ ] Tampered checkpoints, failed reproduction tools and malformed assessor output retain explicit error/unresolved evidence and cannot be reported as successful verification.

### Blocked by

- F1.

## 9. F3 — Complete the real MVP acceptance walkthrough and report

Milestone: MVP 3. Type: HITL. Label: `ready-for-human`.

### What to build

Finish the operator workflow with one complete local report and a reproducible acceptance walkthrough covering the actual generated portal, development sessions, checkpoint assessments and final security investigation. The owner should use the delivered commands, inspect the application, and understand the results without hand-authoring runtime JSON or reconstructing paths. Reuse compatible evidence from earlier slices instead of repeating model calls just to demonstrate an unchanged behavior.

### Acceptance criteria

- [ ] Owner walkthrough exercises the real simple entry point for development, status, restricted preview, checkpoint evaluation, final assessment and report exports with reusable configuration and clear output locations.
- [ ] The complete report links ten genuine generated source snapshots, their primary assessments/reruns, final assessment/adjudication records and exact versions. Missing evidence is explicit and blocks claims of full completion.
- [ ] JSON, CSV and readable outputs agree on all real statuses, measured development/checkpoint/final-assessment resources, retries, unknowns and evidence references.
- [ ] Reconcile summary totals against individual retained records, verify originals remain intact and verify evaluator artifacts/results remain inaccessible to development.
- [ ] Record each milestone's observed passes, failures, skips, blockers and operator friction; publish only sanitized summaries, retaining raw private evidence outside public issues/development contexts.
- [ ] Milestone 3 is accepted only after real behavior is demonstrated. This portal MVP acceptance neither closes #19's five-application readiness work nor authorizes the full pilot or any paid run.

### Blocked by

- D3.
- E3.
- F2.
