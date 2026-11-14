# Published baseline implementation issues

Status: owner approved the breakdown and all 19 issues were published to GitHub on 2026-11-14. Source: the approved baseline pilot specification. Dependencies and readiness labels were verified against GitHub. There is no parent issue. Issue numbers match the original draft IDs; no benchmark implementation or pilot execution was performed.

The source spec has no numbered user stories. Each slice therefore names the capability it covers rather than inventing story IDs. AFK means implementable without a design interview; HITL identifies an actual owner review. Readiness dependencies are conjunctive.

All implementation verification uses local controls or simulated agent output unless live execution is separately requested. No paid calls, full pilot launch, benchmark solutions in public issue bodies, or later intervention implementation are included. Agent-authored implementation choices must preserve ordinary Codex behavior and hidden evaluation boundaries.

## 1. [Run one fixture task from CLI to scored checkpoint](https://github.com/SrFlipFlop/principiis-obsta/issues/1)

**Type:** AFK  
**Covers:** Task delivery, execution, artifacts and reporting

### What to build

Deliver a minimal end-to-end command-line path: select one ordinary-development task, deliver its visible contract to an injected test executor, preserve its completed artifact, execute an independent hidden check and produce structured results plus a readable report. Use a harmless engineering fixture, not an additional benchmark application. Choose a simple controller language and filesystem representation and document the choice. Establish a small documented task/checkpoint interface that later application authors can use; avoid an adapter framework or service architecture.

### Acceptance criteria

- [ ] A single reproducible command demonstrates request → executor → recoverable snapshot → executable check → report without invoking a model.
- [ ] Artifacts identify run, task/condition version, attempt and checkpoint; results distinguish joint pass, candidate failure, evaluator error and incomplete execution.
- [ ] The executor receives visible task content only; hidden tests and researcher context are outside its workspace.
- [ ] Behavioral tests cover passing, failing and evaluator-error fixture outcomes; no production application or security intervention is introduced.

### Blocked by

None — can start immediately

## 2. [Execute incremental sequences with fresh step sessions](https://github.com/SrFlipFlop/principiis-obsta/issues/2)

**Type:** AFK  
**Covers:** Incremental disclosure and project persistence

### What to build

Extend the executable path to an ordered multi-step application sequence. Each step starts a fresh executor session with current/cumulative requirements and its own prior project files, including agent-written notes. Future requests, previous conversation transcripts, external session memory and hidden evaluation remain unavailable. Preserve completed snapshots and advance after candidate functional/security failures without resetting to reference code.

### Acceptance criteria

- [ ] A multi-step fixture proves file/note persistence and fresh session identity, while future-step sentinel content is absent from the development context.
- [ ] A completed but failing checkpoint is retained and followed by the next request; later success does not erase failure history.
- [ ] Task validation rejects missing/duplicate step identifiers and inconsistent sequence versions before starting.
- [ ] Initial workspaces are empty application projects; different runs never inherit each other’s artifacts.

### Blocked by

[#1](https://github.com/SrFlipFlop/principiis-obsta/issues/1)

## 3. [Run ordinary Codex through the sequence controller](https://github.com/SrFlipFlop/principiis-obsta/issues/3)

**Type:** AFK  
**Covers:** Real coding-agent execution and passive evidence

### What to build

Add the first real execution path using ordinary noninteractive Codex and existing subscription authentication. Support explicit execution-time model/settings, ordinary tools, dependency installation and documentation/network access under configured permissions. Do not add security instructions, skills, reviews or behavioral hooks. Keep project/research instructions and hidden artifacts out of task contexts while retaining intended ordinary harness behavior. Record resolved configuration, command/file/tool events, exposed summaries, stderr and exit status without recording secrets.

### Acceptance criteria

- [ ] CLI selection invokes Codex per step with the intended visible request and workspace, preserving ordinary development behavior.
- [ ] Contract tests using a fake executable/event stream verify invocation, output capture, failures and no researcher-context/future-request leakage.
- [ ] Configuration identifies intended access mode, harness/version and execution settings; absent usage/configuration fields remain unknown rather than guessed.
- [ ] No live model run, paid API call or authentication change is required to implement or verify this issue.

### Blocked by

[#2](https://github.com/SrFlipFlop/principiis-obsta/issues/2)

## 4. [Inspect per-step and total resource consumption](https://github.com/SrFlipFlop/principiis-obsta/issues/4)

**Type:** AFK  
**Covers:** Time, tokens, memory and cost accounting

### What to build

Make a completed or failed sequence inspectable from the CLI with per-attempt/step totals for elapsed time, provider-reported token categories and host-side agent/tool memory. Preserve measurement scope/method and unavailable values. Keep development and independent evaluation separate and support future intervention-stage attribution without implementing interventions. Distinguish actual spending from dated API-equivalent estimates.

### Acceptance criteria

- [ ] Reports retain incomplete attempts and aggregate unique usage exactly once, including cached/reasoning categories without double counting.
- [ ] Wall time and summed stage durations are distinguished; process/container memory scope and measurement limits are explicit.
- [ ] Missing usage is reported as unknown; subscription spending is never fabricated from token estimates.
- [ ] Controlled clock/process/event fixtures verify totals, unavailable metrics and interrupted-child cleanup without model calls.

### Blocked by

[#3](https://github.com/SrFlipFlop/principiis-obsta/issues/3)

## 5. [Resume completed checkpoints and preserve interrupted attempts](https://github.com/SrFlipFlop/principiis-obsta/issues/5)

**Type:** AFK  
**Covers:** Recoverable progress and explicit retry

### What to build

Provide checkpoint-boundary resume. Keep interrupted workspaces, logs and resource evidence as incomplete attempts. An explicitly requested retry receives a new attempt record and starts from the last completed snapshot, or the empty initial project for step one. Do not recover live conversation sessions, silently retry until success or overwrite historical evidence.

### Acceptance criteria

- [ ] Interrupt/resume tests show completed steps are not regenerated and the next step starts in a fresh session.
- [ ] An interrupted attempt is immutable evidence; explicit retry restores the prior completed state and gets a distinct identity.
- [ ] Candidate failure, controller interruption and evaluator error remain distinct, with resource usage preserved.
- [ ] Resume rejects mismatched task/configuration versions unless an explicit new run is created; no implicit pooling.

### Blocked by

[#3](https://github.com/SrFlipFlop/principiis-obsta/issues/3)

## 6. [Evaluate browser and backend behavior in an isolated checkpoint](https://github.com/SrFlipFlop/principiis-obsta/issues/6)

**Type:** AFK  
**Covers:** Executable primary oracles and qualification

### What to build

Evaluate a retained full-stack fixture through a browser and direct backend requests in disposable restricted environments, without modifying the source snapshot or returning results to development. Add controlled integration services and deterministic reset/readiness behavior. Preserve ordinary development network access separately from restricted application/evaluator execution. Provide the narrow evaluation interface needed by benchmark authors.

### Acceptance criteria

- [ ] A fixture with UI-only authorization fails a direct-backend security check while legitimate browser/API flows are checked independently.
- [ ] Property-satisfying, property-violating, broken/reject-all and alternative-valid controls exercise oracle behavior; repeated unchanged controls detect flakiness.
- [ ] Application environments have explicit resource/network/mount/privilege constraints and no production/model credentials; evaluator/controller failures do not become security passes.
- [ ] Checks preserve evidence and report functionality, security assessability and joint results; revised evaluators can consistently rescore retained artifacts.

### Blocked by

[#1](https://github.com/SrFlipFlop/principiis-obsta/issues/1)

## 7. [Investigate additional vulnerabilities with an independent evaluator agent](https://github.com/SrFlipFlop/principiis-obsta/issues/7)

**Type:** AFK  
**Covers:** Independent agent investigation and evidence

### What to build

Add a separate evaluator-agent stage over retained checkpoints. It can run hidden checks and investigate additional issues in the evaluation environment. Primary scores remain those of predefined executable checks; supplemental claims need reproducible evidence and verified/rejected/unresolved status. Keep this stage distinct from future local review and give no results to the writer.

### Acceptance criteria

- [ ] The evaluation CLI records evaluator configuration, prompt version, tool evidence and separate resource usage.
- [ ] Seeded fixture findings demonstrate evidence linkage, root-cause deduplication and verified/rejected/unresolved handling; unsupported claims cannot count as verified.
- [ ] Primary results are not silently changed by novel findings; oracle revisions and rescoring are explicit.
- [ ] Tests use simulated agent responses and local executable evidence; actual evaluator/model settings and live execution remain deferred.

### Blocked by

[#3](https://github.com/SrFlipFlop/principiis-obsta/issues/3), [#6](https://github.com/SrFlipFlop/principiis-obsta/issues/6)

## 8. [Document portal: qualify the initial build and first two changes](https://github.com/SrFlipFlop/principiis-obsta/issues/8)

**Type:** HITL  
**Covers:** Document portal sequence authoring and oracle validation

### What to build

Author a runnable benchmark package for document portal using Python: three visible developer requests (initial build plus two changes), application-specific frontend choices, minimal external API/browser contracts and hidden functional/security checks. Select ordinary frameworks/database without disabling normal safeguards. Work as benchmark author, not as the evaluated developer. Keep the initial development workspace empty; property controls/reference fixtures stay evaluator-only. Establish repeated risk opportunities across functionalities and reuse the suite’s authoring interface. No subscription baseline generation is part of authoring. Review the first package’s security-expectation rubric and ambiguous-policy treatment with the owner before treating it as the authoring example for the suite.

### Acceptance criteria

- [ ] Three incrementally released requests specify externally testable behavior in the assigned Python ecosystem, leaving unneeded internal details open.
- [ ] Each checkpoint has legitimate browser/backend checks and justified security properties labeled stated, implied or evaluator-only; ambiguous expectations are explicitly resolved or separately reported.
- [ ] Hidden checks are qualified using property-satisfying, violating, reject-all and alternative-valid controls, including repeated risk opportunities and clean state reset.
- [ ] The platform can load and evaluate the package against evaluator-only controls; no solution, hidden test or future task is shipped to the developer workspace. Owner review of the rubric and property mappings is recorded.

### Blocked by

[#6](https://github.com/SrFlipFlop/principiis-obsta/issues/6)

## 9. [Document portal: complete the ten-step evolution](https://github.com/SrFlipFlop/principiis-obsta/issues/9)

**Type:** AFK  
**Covers:** Document portal full application sequence

### What to build

Extend the qualified document portal package from three to ten steps. Author seven further requests that challenge earlier assumptions and interact with existing behavior, mixing features, changed requirements, predefined bug reports and refactoring across the complete sequence. Vary request detail deliberately and freeze/version ordinary task content. Extend cumulative/changed functional and security checks without leaking future tasks or injecting defects into evaluated code.

### Acceptance criteria

- [ ] Exactly ten steps are loadable, with explicit cumulative requirements and supersession rules; no contradictory stale checks reject legitimate requirement changes.
- [ ] The full sequence has repeated opportunities for shared risk classes plus application-specific risks, with property/checkpoint traceability.
- [ ] Bug reports are meaningful even when generated code lacks the suspected defect; refactors specify preserved observable behavior and no request uses live hidden findings.
- [ ] All ten checkpoints pass oracle qualification on evaluator-only controls and support reproducible browser/backend evaluation; no live development-agent run is needed.

### Blocked by

[#8](https://github.com/SrFlipFlop/principiis-obsta/issues/8)

## 10. [Customer-support desk: qualify the initial build and first two changes](https://github.com/SrFlipFlop/principiis-obsta/issues/10)

**Type:** AFK  
**Covers:** Customer-support desk sequence authoring and oracle validation

### What to build

Author a runnable benchmark package for customer-support desk using PHP: three visible developer requests (initial build plus two changes), application-specific frontend choices, minimal external API/browser contracts and hidden functional/security checks. Select ordinary frameworks/database without disabling normal safeguards. Work as benchmark author, not as the evaluated developer. Keep the initial development workspace empty; property controls/reference fixtures stay evaluator-only. Establish repeated risk opportunities across functionalities and reuse the suite’s authoring interface. No subscription baseline generation is part of authoring.

### Acceptance criteria

- [ ] Three incrementally released requests specify externally testable behavior in the assigned PHP ecosystem, leaving unneeded internal details open.
- [ ] Each checkpoint has legitimate browser/backend checks and justified security properties labeled stated, implied or evaluator-only; ambiguous expectations are explicitly resolved or separately reported.
- [ ] Hidden checks are qualified using property-satisfying, violating, reject-all and alternative-valid controls, including repeated risk opportunities and clean state reset.
- [ ] The platform can load and evaluate the package against evaluator-only controls; no solution, hidden test or future task is shipped to the developer workspace.

### Blocked by

[#6](https://github.com/SrFlipFlop/principiis-obsta/issues/6), [#8](https://github.com/SrFlipFlop/principiis-obsta/issues/8)

## 11. [Customer-support desk: complete the ten-step evolution](https://github.com/SrFlipFlop/principiis-obsta/issues/11)

**Type:** AFK  
**Covers:** Customer-support desk full application sequence

### What to build

Extend the qualified customer-support desk package from three to ten steps. Author seven further requests that challenge earlier assumptions and interact with existing behavior, mixing features, changed requirements, predefined bug reports and refactoring across the complete sequence. Vary request detail deliberately and freeze/version ordinary task content. Extend cumulative/changed functional and security checks without leaking future tasks or injecting defects into evaluated code.

### Acceptance criteria

- [ ] Exactly ten steps are loadable, with explicit cumulative requirements and supersession rules; no contradictory stale checks reject legitimate requirement changes.
- [ ] The full sequence has repeated opportunities for shared risk classes plus application-specific risks, with property/checkpoint traceability.
- [ ] Bug reports are meaningful even when generated code lacks the suspected defect; refactors specify preserved observable behavior and no request uses live hidden findings.
- [ ] All ten checkpoints pass oracle qualification on evaluator-only controls and support reproducible browser/backend evaluation; no live development-agent run is needed.

### Blocked by

[#10](https://github.com/SrFlipFlop/principiis-obsta/issues/10)

## 12. [Team expense manager: qualify the initial build and first two changes](https://github.com/SrFlipFlop/principiis-obsta/issues/12)

**Type:** AFK  
**Covers:** Team expense manager sequence authoring and oracle validation

### What to build

Author a runnable benchmark package for team expense manager using C#/.NET: three visible developer requests (initial build plus two changes), application-specific frontend choices, minimal external API/browser contracts and hidden functional/security checks. Select ordinary frameworks/database without disabling normal safeguards. Work as benchmark author, not as the evaluated developer. Keep the initial development workspace empty; property controls/reference fixtures stay evaluator-only. Establish repeated risk opportunities across functionalities and reuse the suite’s authoring interface. No subscription baseline generation is part of authoring.

### Acceptance criteria

- [ ] Three incrementally released requests specify externally testable behavior in the assigned C#/.NET ecosystem, leaving unneeded internal details open.
- [ ] Each checkpoint has legitimate browser/backend checks and justified security properties labeled stated, implied or evaluator-only; ambiguous expectations are explicitly resolved or separately reported.
- [ ] Hidden checks are qualified using property-satisfying, violating, reject-all and alternative-valid controls, including repeated risk opportunities and clean state reset.
- [ ] The platform can load and evaluate the package against evaluator-only controls; no solution, hidden test or future task is shipped to the developer workspace.

### Blocked by

[#6](https://github.com/SrFlipFlop/principiis-obsta/issues/6), [#8](https://github.com/SrFlipFlop/principiis-obsta/issues/8)

## 13. [Team expense manager: complete the ten-step evolution](https://github.com/SrFlipFlop/principiis-obsta/issues/13)

**Type:** AFK  
**Covers:** Team expense manager full application sequence

### What to build

Extend the qualified team expense manager package from three to ten steps. Author seven further requests that challenge earlier assumptions and interact with existing behavior, mixing features, changed requirements, predefined bug reports and refactoring across the complete sequence. Vary request detail deliberately and freeze/version ordinary task content. Extend cumulative/changed functional and security checks without leaking future tasks or injecting defects into evaluated code.

### Acceptance criteria

- [ ] Exactly ten steps are loadable, with explicit cumulative requirements and supersession rules; no contradictory stale checks reject legitimate requirement changes.
- [ ] The full sequence has repeated opportunities for shared risk classes plus application-specific risks, with property/checkpoint traceability.
- [ ] Bug reports are meaningful even when generated code lacks the suspected defect; refactors specify preserved observable behavior and no request uses live hidden findings.
- [ ] All ten checkpoints pass oracle qualification on evaluator-only controls and support reproducible browser/backend evaluation; no live development-agent run is needed.

### Blocked by

[#12](https://github.com/SrFlipFlop/principiis-obsta/issues/12)

## 14. [Integration/workflow dashboard: qualify the initial build and first two changes](https://github.com/SrFlipFlop/principiis-obsta/issues/14)

**Type:** AFK  
**Covers:** Integration/workflow dashboard sequence authoring and oracle validation

### What to build

Author a runnable benchmark package for integration/workflow dashboard using Go: three visible developer requests (initial build plus two changes), application-specific frontend choices, minimal external API/browser contracts and hidden functional/security checks. Select ordinary frameworks/database without disabling normal safeguards. Work as benchmark author, not as the evaluated developer. Keep the initial development workspace empty; property controls/reference fixtures stay evaluator-only. Establish repeated risk opportunities across functionalities and reuse the suite’s authoring interface. No subscription baseline generation is part of authoring.

### Acceptance criteria

- [ ] Three incrementally released requests specify externally testable behavior in the assigned Go ecosystem, leaving unneeded internal details open.
- [ ] Each checkpoint has legitimate browser/backend checks and justified security properties labeled stated, implied or evaluator-only; ambiguous expectations are explicitly resolved or separately reported.
- [ ] Hidden checks are qualified using property-satisfying, violating, reject-all and alternative-valid controls, including repeated risk opportunities and clean state reset.
- [ ] The platform can load and evaluate the package against evaluator-only controls; no solution, hidden test or future task is shipped to the developer workspace.

### Blocked by

[#6](https://github.com/SrFlipFlop/principiis-obsta/issues/6), [#8](https://github.com/SrFlipFlop/principiis-obsta/issues/8)

## 15. [Integration/workflow dashboard: complete the ten-step evolution](https://github.com/SrFlipFlop/principiis-obsta/issues/15)

**Type:** AFK  
**Covers:** Integration/workflow dashboard full application sequence

### What to build

Extend the qualified integration/workflow dashboard package from three to ten steps. Author seven further requests that challenge earlier assumptions and interact with existing behavior, mixing features, changed requirements, predefined bug reports and refactoring across the complete sequence. Vary request detail deliberately and freeze/version ordinary task content. Extend cumulative/changed functional and security checks without leaking future tasks or injecting defects into evaluated code.

### Acceptance criteria

- [ ] Exactly ten steps are loadable, with explicit cumulative requirements and supersession rules; no contradictory stale checks reject legitimate requirement changes.
- [ ] The full sequence has repeated opportunities for shared risk classes plus application-specific risks, with property/checkpoint traceability.
- [ ] Bug reports are meaningful even when generated code lacks the suspected defect; refactors specify preserved observable behavior and no request uses live hidden findings.
- [ ] All ten checkpoints pass oracle qualification on evaluator-only controls and support reproducible browser/backend evaluation; no live development-agent run is needed.

### Blocked by

[#14](https://github.com/SrFlipFlop/principiis-obsta/issues/14)

## 16. [Online marketplace: qualify the initial build and first two changes](https://github.com/SrFlipFlop/principiis-obsta/issues/16)

**Type:** AFK  
**Covers:** Online marketplace sequence authoring and oracle validation

### What to build

Author a runnable benchmark package for online marketplace using TypeScript/Node.js: three visible developer requests (initial build plus two changes), application-specific frontend choices, minimal external API/browser contracts and hidden functional/security checks. Select ordinary frameworks/database without disabling normal safeguards. Work as benchmark author, not as the evaluated developer. Keep the initial development workspace empty; property controls/reference fixtures stay evaluator-only. Establish repeated risk opportunities across functionalities and reuse the suite’s authoring interface. No subscription baseline generation is part of authoring.

### Acceptance criteria

- [ ] Three incrementally released requests specify externally testable behavior in the assigned TypeScript/Node.js ecosystem, leaving unneeded internal details open.
- [ ] Each checkpoint has legitimate browser/backend checks and justified security properties labeled stated, implied or evaluator-only; ambiguous expectations are explicitly resolved or separately reported.
- [ ] Hidden checks are qualified using property-satisfying, violating, reject-all and alternative-valid controls, including repeated risk opportunities and clean state reset.
- [ ] The platform can load and evaluate the package against evaluator-only controls; no solution, hidden test or future task is shipped to the developer workspace.

### Blocked by

[#6](https://github.com/SrFlipFlop/principiis-obsta/issues/6), [#8](https://github.com/SrFlipFlop/principiis-obsta/issues/8)

## 17. [Online marketplace: complete the ten-step evolution](https://github.com/SrFlipFlop/principiis-obsta/issues/17)

**Type:** AFK  
**Covers:** Online marketplace full application sequence

### What to build

Extend the qualified online marketplace package from three to ten steps. Author seven further requests that challenge earlier assumptions and interact with existing behavior, mixing features, changed requirements, predefined bug reports and refactoring across the complete sequence. Vary request detail deliberately and freeze/version ordinary task content. Extend cumulative/changed functional and security checks without leaking future tasks or injecting defects into evaluated code.

### Acceptance criteria

- [ ] Exactly ten steps are loadable, with explicit cumulative requirements and supersession rules; no contradictory stale checks reject legitimate requirement changes.
- [ ] The full sequence has repeated opportunities for shared risk classes plus application-specific risks, with property/checkpoint traceability.
- [ ] Bug reports are meaningful even when generated code lacks the suspected defect; refactors specify preserved observable behavior and no request uses live hidden findings.
- [ ] All ten checkpoints pass oracle qualification on evaluator-only controls and support reproducible browser/backend evaluation; no live development-agent run is needed.

### Blocked by

[#16](https://github.com/SrFlipFlop/principiis-obsta/issues/16)

## 18. [Report suite-wide baseline progress and checkpoint outcomes](https://github.com/SrFlipFlop/principiis-obsta/issues/18)

**Type:** AFK  
**Covers:** Suite selection, aggregation, evidence and readable reports

### What to build

Connect application selection to execution/evaluation/resume and produce one suite-level report from local artifacts. Include configuration/provenance, checkpoint outcome history, validated supplemental findings, unresolved claims and resource/cost breakdowns. Support partial suites and evaluator-only reruns. Do not implement a dashboard, leaderboard or later intervention mechanisms.

### Acceptance criteria

- [ ] Fixture suites demonstrate selection of one/multiple applications, partial progress, continuation, explicit retries and evaluator-only runs without regenerating code.
- [ ] Reports retain every candidate/infrastructure/evaluator failure with denominators and distinguish unknown/unassessable security from pass.
- [ ] Resources reconcile with per-attempt evidence; supplementary findings stay separate from primary scores and duplicate root causes are not inflated.
- [ ] Summary makes within-application dependence, single-run limitations, bundled application/stack effects and absent efficacy claims explicit.

### Blocked by

[#2](https://github.com/SrFlipFlop/principiis-obsta/issues/2), [#4](https://github.com/SrFlipFlop/principiis-obsta/issues/4), [#5](https://github.com/SrFlipFlop/principiis-obsta/issues/5), [#6](https://github.com/SrFlipFlop/principiis-obsta/issues/6), [#7](https://github.com/SrFlipFlop/principiis-obsta/issues/7)

## 19. [Review pilot readiness and select execution-time settings](https://github.com/SrFlipFlop/principiis-obsta/issues/19)

**Type:** HITL  
**Covers:** Qualified baseline launch preparation

### What to build

Review the assembled ordinary-development platform and all five ten-step application packages before scheduling actual pilot execution. Resolve only execution-time settings and scientific ambiguities that remain material. Produce a launchable manifest for 50 development sessions, but do not automatically launch the pilot, change account authentication or start paid runs.

### Acceptance criteria

- [ ] Owner reviews the suite/task versions, expectation mappings and oracle-qualification evidence, including any unresolved ambiguous policies.
- [ ] Model/reasoning, subscription access mode, per-step/sequence limits, interruption categories and bounded retry policy are explicitly selected and recorded.
- [ ] An offline/simulated readiness check validates all five ten-step manifests, required toolchains, artifact separation, reporting and checkpoint recovery; development itself is not forced offline.
- [ ] Actual pilot scheduling is an explicit owner action; no paid API use, fine-tuning, intervention comparison or unsupported scientific conclusion is included.

### Blocked by

[#7](https://github.com/SrFlipFlop/principiis-obsta/issues/7), [#9](https://github.com/SrFlipFlop/principiis-obsta/issues/9), [#11](https://github.com/SrFlipFlop/principiis-obsta/issues/11), [#13](https://github.com/SrFlipFlop/principiis-obsta/issues/13), [#15](https://github.com/SrFlipFlop/principiis-obsta/issues/15), [#17](https://github.com/SrFlipFlop/principiis-obsta/issues/17), [#18](https://github.com/SrFlipFlop/principiis-obsta/issues/18)
