> Research record for the paper; not required reading. Current scope and decisions are in [PROJECT.md](../../PROJECT.md). Approval and authorization wording below is dated history, superseded by the four hard rules in [AGENTS.md](../../AGENTS.md). Historical multi-arm pilot, fixed-stack and offline-development suggestions are not current scope.

# Experimental protocol — research proposals and alignment record

## Study units

A **task** consists of (i) a versioned starting repository, (ii) a natural-language feature request, (iii) hidden functional tests, (iv) hidden security invariants / adversarial tests, and (v) test metadata and risk taxonomy visible only to the evaluator. Prefer realistic repository modifications to toy snippets.

An **experimental run** fixes task version, agent harness, model version, treatment, prompt/spec version, allowed tools, environment, and budgets, then logs the implementation and independent evaluation.

## Candidate intervention arms

| Arm | Condition | Attribution question |
| --- | --- | --- |
| C0 | Normal coding agent + feature spec | Baseline |
| C1 | C0 + always-on generic security skill | Does general knowledge help? |
| C2 | C0 + task-specific/on-demand security skill | Is relevant context better than boilerplate? |
| C3 | C0 + explicit security acceptance criteria | Benefit of providing missing facts |
| C4 | C0 + same criteria as C3, structured into threats/assets/boundaries/controls | Benefit of threat-model *structure*, independent of extra facts |
| C5 | Agent derives threat model from ordinary feature spec | Can early analysis discover missing controls? |
| C6 | C0 + local SAST/security-review hook + repair | Detection, feedback, remediation |
| C7 | C0 + budget-matched generic extra review/repair | Is improvement just extra compute? |
| C8 | Combined selected interventions | Possible synergy after individual effects validated |

Avoid a full factorial in the pilot. These conditions require protocol and leakage reviews before use.

## Task candidates

1. **Multi-tenant invoice export**: user A cannot fetch user B's invoice by guessing an ID; authorized fetches still work. Risks: IDOR / broken object-level authorization, tenant isolation.
2. **Webhook receiver**: verify signatures, reject tampered data, enforce bounded replay window/nonces; legitimate requests work.
3. **File upload endpoint**: reject traversal and dangerous file handling; legitimate uploads work.
4. Expansion: password reset, SSRF-safe URL retrieval, diagnostic command execution, session security, and multi-tenant queries. Avoid exposing runnable exploit code outside isolated toy fixtures.

Tasks should look like normal business feature requests; do not leak expected weaknesses through suspicious filenames or visible test descriptions. Tests need positive and negative cases, not just “all requests fail.”

## Initial experimental sizing

**Owner-aligned pilot:** baseline ordinary development only, across an initial set of five full-stack benchmark applications, each with an application sequence, to qualify fresh step sessions, project persistence, hidden checkpoint evaluation, artifact capture and time/token accounting. The owner subsequently selected a five-application target; the five application themes are confirmed in `docs/BENCHMARK_APPLICATIONS.md`; ten steps per application are confirmed; exact feature scope remains open. Use one run per application initially; independent repeats are deferred. No intervention efficacy claim follows from this pilot.

The earlier 36-run, four-arm example is superseded. Add intervention conditions in subsequent phases once baseline mechanics and evaluator validity are qualified. Generic guidance, skills, local review/repair and threat-modeling specifications are candidate later phases; fine-tuning remains deferred and separately scoped. Exact order is not decided. Pilot artifacts may be development/tuning data; do not assume they are confirmatory baseline observations for later conditions without freezing the protocol and addressing version drift. No run is authorized before alignment/spec approval.

## Primary and secondary outcomes

**Primary:** task-level **secure-and-functional pass**: all required functional behaviors pass *and* the predefined security invariants pass. Report denominators and failure/timeout handling. Aggregate at task level and show paired results.

**Secondary:** functional pass, security pass, verified vulnerability count/severity and CWE, first-pass versus repaired vulnerabilities, time, tokens, estimated/provider-reported cost, run failures, reviewer findings, validated true positives, false positives, and review disruption.

**LLM finding counts are not a ground truth.** Keep a fixed-model, blind, versioned reviewer as a secondary discovery instrument, assisted by SAST; deduplicate, verify with executable reproductions, and manually adjudicate ambiguous high-impact claims. Use seeded vulnerable/safe control implementations to calibrate reviewer accuracy before comparing treatments.

## Protocol controls and threats to validity

- **Agent vs model:** Codex versus Claude Code changes more than model weights. Call this an *agent-system* comparison. For model-only comparisons use a common supported harness and equivalent tools, or explicitly note confounding.
- **Budget:** fixing a token cap alone does not equalize inference opportunity. Report context/input sizes, turn limits, review passes, and compute; include a budget-matched nonspecialized review arm for hook studies.
- **Nondeterminism:** independent repeats, paired task design, randomize condition order when feasible, save seeds only where meaningful; never imply determinism from temperature=0.
- **Contamination:** separate hidden tests/reference solutions from generation sandboxes; restrict network/search and Git history access; audit benchmark visibility and model pretraining overlap.
- **Isolation:** disposable containers, no host secrets, no production credentials, bounded CPU/memory/time, disabled/untrusted network by default, least privileges, and tight mount controls.
- **Independent evaluation:** no benchmark agent may see the evaluator prompt, security oracle, reference patch, or researcher notes about the exact answer.
- **Reproducibility:** pin starting commits, dependency lockfiles, model identifiers/dates, agent/client versions, skill content hashes, prompt templates, tool permissions, and result schema. Include failed runs.
- **Human review:** blind adjudication where practicable; publish reviewer agreement and uncertainty. Report task-level uncertainty with task-aware methods; small pilots cannot support sweeping significance claims.
- **Experimental integrity:** a research/implementation assistant is not an evaluated agent. Never transfer benchmark context from main research repository to an agent's isolated working context.

## Runner architecture to *consider*, not implement yet

Separate Task Registry, Agent Adapter(s), Treatment Builder, Isolated Executor, Artifact Store, and Independent Evaluator. Simple Python + pytest + Docker could be sufficient; postpone framework selection until `/grill-with-docs`.

## Publication discipline

Report what happened, including failures, evaluator disagreement, costs, confounds, and non-significant results. Avoid claiming to demonstrate broad “secure by default” properties from a small collection of scenarios. If results are to be published as a new benchmark, use a public development split and held-out evaluation tasks to reduce future contamination.

## Qualification amendments proposed after research — 2026-11-14

These amendments are proposals for alignment, not an approved protocol. See [evaluation critique](03_EVALUATION_VALIDITY.md) for evidence, preregistration fields and failure rules.

- Choose one primary estimand/contrast before sample size: single-run joint success averaged by task is a candidate. Distinguish fixed-task from population inference. Treat the 36-run example as an engineering pilot; three tasks are three task clusters.
- Independently audit C3/C4 clause-level information equivalence, including assumptions and trust boundaries. Record input lengths and preparation costs. C5 discovery is a different mechanism.
- Qualify oracles on property-satisfying, property-violating, reject-all and alternative-valid controls; repeat unchanged artifacts for flakiness. Freeze before comparisons and consistently rescore all affected artifacts after versioned oracle corrections.
- Broken/nonstarting artifacts have joint score zero, with security unassessable. Separate infrastructure/evaluator errors from candidate/budget failures under predeclared bounded retries. Preserve every attempt.
- Preregister task families, treatment hashes, allowed/consumed resources, stopping and checkpoint rules, drift handling, blinding/calibration/adjudication, uncertainty target and multiplicity. A common CLI alone does not isolate model effects.
- Historical research recommendation: C0/C3/C4 could form a narrow comparative study if novelty/equivalence survive review. The owner has since selected a baseline-only mechanics pilot; comparative arms belong to later phases. Reuse versus custom tasks requires a metadata/license/oracle audit; do not implement tasks to decide the research question.

## Aligned task unit: application sequences

Owner confirmed during `/grill-with-docs` that the core unit is an application sequence: initial application development followed by feature changes, retaining the agent-generated code. Compared conditions receive the same ordered tasks in independent runs. Evaluate functionality and applicable security properties at each checkpoint, including regressions. Independence applies between sequence runs; checkpoints within a sequence are dependent. Earlier task/run descriptions must be interpreted accordingly.

Confirmed: incremental development is the main strategy; future feature requests are revealed only when their step begins. The owner also wants a later fresh-build comparison with all final requirements supplied upfront. Upfront development means one agent assignment with normal internal planning, tool use, testing and revision; it does not mean one model response. Comparator budgets and scheduling remain open.

Confirmed: each incremental step uses a fresh agent session, preserving its sequence run's code/project files and accumulated requirements, without previous conversation history. Confirmed: agent-authored files explicitly written inside the project, including notes and development instructions, carry forward and are included in checkpoint snapshots. Prior conversation transcripts and external session memory do not carry forward; hidden evaluation material never enters these files. Agent-written notes may convey observations learned during a permitted local review.

Confirmed: continue the sequence after candidate functional/security failures, retaining generated code and hiding checkpoint results. Do not replace it with reference code or add evaluator-driven repair. Ordinary work on later requests may incidentally fix or worsen earlier defects. Preserve each checkpoint result; later recovery does not erase prior failure. Infrastructure errors and hard execution limits require separate prespecified handling.

Confirmed: ten steps per application (initial build plus nine changes), totaling 50 development sessions/checkpoints for five baseline application runs.

Open: exact step content/order, treatment timing, initial fixtures, resource budgets and sequence-level aggregation. The example document-service sequence is illustrative, not a selected benchmark task. Implementation remains gated on completed alignment and reviewed spec.

The incremental-versus-upfront comparison changes requirement visibility and development history together. It estimates the combined workflow difference; it cannot alone isolate a causal effect of code erosion. Compare equivalent final behavior and security contracts, with final requirement conflicts resolved consistently. No extra security facts should enter one workflow accidentally. These are methodological requirements to refine during alignment, not a finalized experiment.

## Evaluation visibility and local review — confirmed during alignment

Independent checkpoint tests, findings and scores remain hidden from the evaluated agent, including in later step sessions. Agent-written/local development tests remain available under the condition's tool policy. The owner wants local security review as an intervention whose feedback can steer development; this is distinct from independent scoring. The local reviewer must not consume hidden tests, oracle findings or evaluator output.

Confirmed timing: run local security review automatically at the submission boundary, after initial feature implementation and before a pull request would enter pipeline controls; allow bounded repair. The owner favors agent hooks for automatic invocation. Exact native event, enforcement and completion behavior remain implementation choices to validate after alignment. No real remote PR is required by this research decision.

Confirmed: exactly one local review pass and, when findings are returned, one bounded repair phase per development step; no automatic re-review or repeat-until-clean loop. The repair phase may use ordinary editing/testing iterations within its allowance. Reviewer type, finding format, exact repair allowance remain open. Findings may persist through agent-authored project notes under the common persistence policy. Preserve observable review/repair actions to investigate steering, while treating explanations of the agent's internal mechanism as tentative. Pre/post-review snapshots and a budget-matched generic-review control remain protocol guardrails for interpreting review benefits. No reviewer implementation or experiment is approved by this clarification.

## Resource accounting clarified by owner

Time and token consumption must be gathered across all hypotheses/intervention conditions to compare monetary and latency overhead. Include initial development, context/threat analysis where applicable, local reviewer calls, repair and retries; record each stage and aggregate by step and application-sequence run. Separate end-to-end elapsed time from summed stage durations when execution overlaps. Independent evaluation costs are recorded separately from the development workflow.

Preserve provider-reported token categories when exposed (input, cached input, output and reasoning where applicable); record unavailable usage as unknown. Reasoning tokens can be a subset of output tokens: do not double count. Aggregate distinct requests/sessions once rather than adding cumulative totals repeatedly or counting subagents twice. Cost estimates must identify model, dated pricing and caching assumptions; subscription usage and estimated API-equivalent spend differ from actual marginal bills. This accounting requirement does not authorize paid calls.

The owner accepts a separate reviewer agent/session or subagent if hooks can invoke it and return findings. This is conditional on technical feasibility, not a finalized implementation choice. Confirmed: the practical comparison permits measured additional review/repair budget rather than forcing it inside the initial-development allowance. Report total workflow spending as development plus review plus repair and other intervention-specific inference, with stage breakdowns. Do not assume initial development costs are identical: different context or feedback may change them. Compare total overhead relative to the baseline as well as the reviewer line item. A generic extra-review control remains required to distinguish security-specific benefit from extra effort. Exact resource ceilings and reviewer execution remain open; one review and one bounded repair phase per step are confirmed.

## Baseline pilot scope — confirmed

Baseline means ordinary Codex development with normal tools and agent-written tests, without added security guidance, skills, review or behavioral hooks. Do not load this research repository's instructions, Matt Pocock workflow skills or user-level intervention configuration into evaluated task environments. Record and control the normal harness configuration; the model's existing security knowledge is not removed.

The pilot must qualify the complete experimental workflow: selected/versioned application-sequence tasks; delivery of current/cumulative requirements; fresh Codex sessions and retained workspaces; snapshots, logs and outputs; hidden functional/security evaluation; and time, token and memory monitoring. It is not merely a demonstration that the CLI runs. Exact storage layout, task selection, execution interface and evaluator implementation remain unapproved.

Passive instrumentation must be consistent across conditions and must not supply feedback or change development instructions. Prefer external/event-based collection for the baseline; if any diagnostic hook is required, document it explicitly and distinguish it from prohibited behavioral hooks. Include host-side agent/tool memory measurements with a defined scope (process tree/container), units and peak/sampling method; distinguish these from token/context usage. Hosted model memory is not measurable from local process memory. Record unavailable metrics as unknown. Keep controller, generated application and evaluator resource usage separable. Exact measurement method remains open.

## Initial benchmark application scope — confirmed

Owner initially selected 3–5 runnable full-stack benchmark applications, then requested five. This supersedes the single backend-only application recommendation. Each includes frontend and backend, enabling investigation of failures across layers and controls incorrectly enforced only in the UI. This is the software the agent develops, not the research platform. The five themes are confirmed in `docs/BENCHMARK_APPLICATIONS.md`; ten steps per application are confirmed; exact feature scope, stack(s) and step ordering remain open; initially use one run per application. Confirmed: use partial overlap in security-risk coverage across the initial applications, combining shared risks in different application contexts with application-specific risks. The exact risk matrix remains open.

Evaluation requirement to specify: verify user-facing functionality through a browser where appropriate and independently exercise backend behavior, including requests that bypass frontend controls. Do not infer backend protection from a UI restriction. Scope and reliability of those checks need an explicit oracle contract. Three to five applications provide useful coverage but do not by themselves establish redundancy, independence or broad statistical generalization.

## Risk opportunities and deferred repeats

Owner clarified that redundancy means multiple opportunities for the same security risk across different functionalities, within and across applications. An agent may implement a property correctly in one place but omit it elsewhere. Evaluate those opportunities explicitly rather than relying on a single feature for each risk class. Partial cross-application risk overlap is retained.

Initially execute each benchmark application sequence once under the baseline. Independent repeats of identical sequences are deferred to later investigations, not an initial pilot requirement. This supersedes the proposed three-repeat pilot. Report location/feature-specific security results alongside checkpoint functionality and joint success; several findings may share one root cause and must not be counted as independent defects automatically.

This design observes different risk opportunities in realized runs; it does not estimate within-task stochastic variation or precise failure probabilities. Checkpoints/features within an application are dependent. A future repeated-run study must start each sequence from the same initial state without inheriting another run's notes/code; current within-sequence persistence remains unchanged. Preserve all initial outcomes without retry-until-success.

## Initial stack policy — reopened

The owner reopened the earlier common-stack decision to consider differences across Python, Go, JavaScript/TypeScript on Node.js, PHP, C#/.NET and Java. Owner clarified the design: assign different language stacks to different applications, retaining five application sequences and 50 baseline development sessions, without cross-language replicas. Exact subset, mapping, frameworks/database and dependency rules remain open. No stack-specific implementation is approved. Do not infer the research platform stack from this choice. Local read-only inspection found Python 3.12.3, Node 24.14.1, npm 11.21.2, uv and a Docker executable; no package installation or Docker daemon validation was performed.

Interpretation: heterogeneous application/stack assignments provide ecosystem coverage. Comparisons of interventions within each assigned application remain possible, but application differences must not be presented as isolated language effects. The earlier 300-session cross-product calculation is not the selected design.

### Backend mapping confirmed

Document portal: Python; customer-support desk: PHP; team expense manager: C#/.NET; integration/workflow dashboard: Go; online marketplace: TypeScript/Node.js. Java is deferred. Retain the same assigned backend for each application across future intervention conditions. Backend frameworks, frontend policy and database choices remain open. See `docs/BENCHMARK_APPLICATIONS.md`.

### Application-specific frontend policy confirmed

Owner accepted application-specific frontend approaches. Owner clarified that creativity refers to the benchmark author selecting scenarios and frontend approaches while authoring benchmark tickets. Exact framework selections and evaluated-agent architectural freedom remain open. Freeze released task constraints consistently across compared conditions. Researcher-created application contracts/evaluators are not themselves the generated implementations being scored. No reference implementation or evaluator materials may leak into evaluated contexts.

## Initial workspace and developer requests — confirmed

Step one starts from an empty project workspace with the runtime/toolchain prepared, the first request and the author-selected technology constraints. Do not supply an implemented application skeleton or author-provided security/architecture decisions. Exact prepared dependencies, tool access and launch contract remain to be specified. Subsequent steps simulate developer work requests during a project, retaining the evaluated agent's own files.

The ordinary request sequence is the shared task substrate. Later interventions can augment request delivery or preparation; the owner specifically envisions threat-modeling instructions before development in the corresponding condition. Exact instructions, timing, requirement provenance, generated artifacts and delivery mechanism are deferred until that intervention is scoped. Do not silently equate this with either C3/C4 supplied facts or C5 agent-inferred threat discovery. Keep baseline requests free of those added instructions; task variants must be versioned and their information differences declared.

## Mixed developer requests — confirmed

The ten-step sequences include new features, changes to requirements, predefined bug-fix requests and refactoring. This adopts the general evolving-requirements principle; do not assert that SlopCodeBench tests this exact task mix without source verification. Exact proportions and ordering remain open.

Benchmark authors must reconcile new and earlier observable requirements so that hidden tests do not penalize legitimate changed behavior. Bug-fix requests are preauthored and independent of the actual run's hidden scores/findings; they must be meaningful even if the generated code does not exhibit the suspected defect. They do not justify injecting defects or swapping in author code. Refactor requests must define behavior that should remain invariant. These contract details require specification before implementation.

## Minimal external API contracts — confirmed

Each step supplies author-defined routes, request/response formats and observable behavior sufficient for independent evaluation. Internal architecture and frontend design are not prescribed beyond agreed technology constraints. Tests must distinguish contract violations from implementation freedom and avoid guessing generated endpoint names. Frontend evaluation contracts, security-invariant provenance and exact contract versioning remain open. Precise external behavior does not require prescribing internal structure or revealing future requests.

## Variable request detail — owner clarification

Owner wants a mixture of detailed and rushed/underspecified developer requests. Some security checks follow directly from visible business context; other security-relevant requirements or assumptions may be omitted to represent real development. The proposal to require every hidden security check to follow from visible context was not adopted. Minimal API contracts still provide the interface needed for evaluation, without necessarily resolving every security-policy detail.

Benchmark authors must distinguish task-visible explicit requirements, requirements implied by visible context, and researcher-selected security expectations not established by the request. For the last category, record the assumption and rationale in hidden evaluator metadata; do not report a failure as disobedience to a stated requirement. Unresolved policy choices may need adjudication or separate reporting rather than an arbitrary hidden pass/fail. Exact classification and scoring policy remain open.

Later security-spec/threat-model conditions may supply previously omitted facts; their effect then includes information provision and cannot automatically be attributed to reasoning or presentation alone. Request-detail level is a task characteristic to control and report, not an excuse to change baseline requests opportunistically after observing outcomes. Confirmed: the benchmark author fixes each ordinary request and its detail level in advance, keeping that base request identical across compared conditions. Interventions add separately versioned guidance/preparation; any added security facts must be recorded. Pilot-driven revisions require new task versions and must be frozen before comparative results are collected.

## Initial access mode — confirmed

Use the owner's existing Codex subscription for the baseline pilot. Paid API experiments remain unauthorized. Record access mode without recording credentials. Actual subscription spending, available token usage and estimated API-equivalent costs are distinct quantities; do not describe estimates as incurred API bills. Subscription capacity and interruptions constrain scheduling; exact pause/retry rules remain open. Model identifier/reasoning selection is deliberately deferred until pilot execution; version-drift policy and per-step resource limits remain to be agreed. No execution is authorized before alignment and spec approval.

### Model choice deferred by owner

Owner reports current usage as GPT-6.1-Sol with default settings, but explicitly defers the study's model/reasoning choice until the first pilot is executed. This report is not an execution pin. Do not block scaffolding specification on selecting a model now. The execution interface must accept explicit model/settings and record resolved configuration when available; freeze the selected configuration for any eventual comparison. Priority is task delivery, isolated agent execution, benchmark definitions, artifact retention, monitoring and the independent evaluator.

Read-only local inspection found no explicit top-level model/reasoning settings or project config; no account/model request was made. Exact execution settings and paid-run authorization remain future decisions.

## Independent evaluator agent — confirmed

Owner confirmed an independent evaluator agent that runs hidden checks and investigates additional vulnerabilities. Predefined executable functional/security checks determine primary scoring; the agent's finding counts do not. Supplementary claims require reproducible evidence and verified/rejected/unresolved status. Hidden evaluation remains independent of any local-review intervention.

Evaluate retained checkpoint artifacts to track functionality/security over the sequence, with a final sequence report. Newly discovered issues do not silently rewrite primary scores: document oracle revisions and consistently rescore affected artifacts if needed. Exact evaluator tools, isolation, validation/adjudication workflow, prompts and reports remain to be specified. Evaluator/model choices can be supplied at execution time and recorded separately from developer settings. No model experiments or evaluator implementation are started by this agreement.

## Initial platform interface — confirmed

Use a command-line research platform with local structured artifacts and human-readable reports; no initial web dashboard. It must support application/condition selection, sequence execution, resume, checkpoint evaluation and inspection of time/token/memory usage. Exact commands, schemas, directory layout, controller language and resume/retry semantics remain open. Local results do not imply permission to place hidden evaluator materials in development workspaces or commit private traces.

## Checkpoint-boundary resume — confirmed

Initial resume operates at completed development-step boundaries. Preserve completed artifacts and resume the next request in a fresh step session. If execution is interrupted mid-step, retain partial workspace, logs and recorded resource consumption as an incomplete attempt. An explicit retry starts from the previous completed checkpoint (or original empty-project state for step one), with a new attempt record; never silently overwrite the incomplete attempt.

Do not implement live agent-session recovery as an initial requirement. An interruption is distinct from a completed but functionally/security-failing step, which still advances under the agreed continuation policy. Classify interruptions, retry limits and evaluator-only resume behavior in the eventual spec. Include incomplete-attempt resource consumption in reported overhead and report successful-retry totals separately where relevant.

## Realistic development workflow — owner clarification

The owner rejected an offline/preinstalled-dependencies-only development policy as unnecessary complexity. Preserve ordinary Codex tools, dependency installation and documentation/network access under normal permissions. Vary security interventions, not routine development access. Record that configuration and keep it comparable across conditions. Generated-application/evaluator isolation and hidden-test separation remain intact.

Consolidated scope was approved in the [baseline pilot spec](../archive/BASELINE_PILOT_SPEC.md) (now archived; see `PROJECT.md`). Routine implementation details should be resolved simply rather than expanded into research decisions.
