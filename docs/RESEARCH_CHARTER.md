> Owner approved [baseline pilot scope](BASELINE_PILOT_SPEC.md) on 2026-11-14 following `/grill-with-docs`. Candidate research questions/hypotheses below remain proposals for later phases; alignment history is retained for rationale.

# Research charter — baseline scope aligned

## Problem statement

In AI-assisted SDLCs, a coding agent can produce code that passes functional tests while violating security properties. A traditional AppSec response is to scan and review downstream. Principiis Obsta investigates **preventive security interventions inside the development process**, particularly risk-aware specifications, context selection, and immediate local feedback.

This is an **experimental research project**. It is not a proposal to remove CI/CD defenses or to build a competing scanner. Protect any nonpublic employer data; do not use corporate code, confidential vulnerabilities, or internal standards in a public benchmark without explicit authorization.

## Primary research question

How much do security interventions at different stages of autonomous software development improve the security **and functionality** of generated application changes, controlling for agent/model choice, tools, computation, and task?

## Candidate research questions

- **RQ1 — Knowledge:** Does generic secure-coding guidance improve security versus baseline? Does targeted/on-demand context perform better than always-loaded guidance?
- **RQ2 — Security requirements:** Does adding explicit security acceptance criteria help? Does *structuring exactly the same requirements* as a threat model add further benefit?
- **RQ3 — Threat discovery:** When the agent must infer threats from ordinary feature specs, can an early threat-modeling intervention discover missing requirements and improve security?
- **RQ4 — Prevention vs repair:** Do early design interventions outperform local scan/review-and-repair, at equal time or inference budget? How much security gain occurs at initial generation versus post-review remediation?
- **RQ5 — Generalization:** Are improvements consistent across agent systems and, where comparable, different models under the same harness? Are smaller local models more sensitive to targeted guidance?
- **RQ6 — Efficiency:** What are functional, security, monetary, token, latency, reviewer false-positive, and workflow disruption costs?

These are candidate questions, **not pre-registered hypotheses or settled priorities**. Shrink scope after objectives alignment.

## Plausible hypotheses — not findings

- Relevant feature-specific security requirements may help more than vague “write secure code” instructions.
- Threat modeling may improve initial design decisions, but also introduce irrelevant risks or consume context.
- Review hooks may improve final security while adding compute, latency, and false positives.
- A stronger model may already know security facts but still miss application-specific trust boundaries.
- Targeted small-model risk identification may be cheaper than a full security-review model, but this requires evaluation before fine-tuning.

## Intended research deliverables

- Reproducible, open-source benchmark runner and task format (only after specs are approved).
- Small set of realistic security-sensitive software-development tasks with functional and behavioral security tests.
- Versioned security interventions and harness/model adapters.
- Raw run artifacts, scoring definitions, analysis, uncertainty, failures and limitations.
- A technical report/blog post, optionally refined into a workshop/paper submission.

## Non-goals for initial phase

- Fine-tuning a model; production integrations; enterprise DevSecOps productization.
- Replacing CI/CD verification or claiming proof of security from a passing scan.
- Thousands of tasks, excessive infrastructure, or optimizing a leaderboard position.
- Benchmarking prompt-injection robustness of the *coding agent itself* (separate research thread from the generated application's vulnerabilities).

## Research refresh — 2026-11-14

The [four-track synthesis](research/05_SYNTHESIS.md) narrows the novelty options: prior work already tests security guidance, contextual requirements, risk selection and repair. No claim or arm is approved. A candidate contribution is separating identical security information from threat-model representation; a transparent replication is also valid. All four original intervention families remain in scope as research directions, with training/combined interventions deferred. Generalization must match the sampled task population, and a publishable null/negative result is an owner-level decision.

## Owner clarification during alignment — 2026-11-14

The goal is to investigate multiple hypotheses through experimentation, without selecting a preferred conclusion in advance. The intended initial deliverable includes a reusable test environment that executes Codex to develop security-sensitive applications and independently evaluates the outputs for validated security issues and functionality. Additional harnesses and then additional models are possible later extensions, not initial requirements. The specific initial model remains open.

The owner also wants to investigate security-related behavior during development. Whether observable traces can support useful process analysis remains to be established; exposed summaries must not be treated as complete private reasoning or proof of the causal mechanism. Shared tasks across compared intervention conditions are confirmed; process-analysis methods and initial experiment scope remain open. Implementation still requires completion of alignment and a reviewed spec. The earlier suggested C3/C4 focus is a recommendation, not an owner-selected objective.

### Task-selection direction clarified by owner

Compare intervention conditions on shared development tasks with fresh runs. The owner favors ordinary security-sensitive features whose risk is implicit in the task, with candidate domains including outbound URL fetching, SQL-backed queries and web rendering. Start from relevant existing secure-development studies/benchmarks where suitable rather than assume a wholly new benchmark is required. Exact sources, tasks and reuse/custom balance remain open.

Methodological recommendation, not yet an owner decision: seek realistic opportunities for known vulnerability classes, while avoiding prompts that force an insecure implementation or tests that enforce unstated arbitrary behavior. Do not select the final evaluation set solely because the chosen baseline fails on it.

### Whole applications, features and evolution

Owner wants both whole-application development and security-sensitive feature tasks represented in the research program. Their relative scope in the first experiment remains open. The owner challenges the assumption that small, cleanly specified changes sufficiently represent real development and proposes SlopCodeBench-inspired evolving requirements and accumulated code history. Owner subsequently confirmed application sequences as the core experimental unit: initial application development followed by feature requests, preserving generated code and evaluating functionality/security at checkpoints. Conditions receive identical task order in independent runs. Sequence length, initial fixtures and detailed protocol remain open.

Hypothesis to investigate: security interventions may differ in their ability to preserve security across successive changes. Complexity/code erosion must not be assumed to imply vulnerabilities. Distinguish requirement growth from history effects before attributing security degradation to accumulated debt.

### Requirement visibility confirmed

Incremental development is the main test strategy: each new request is revealed at its step. The owner also requests a later comparison giving all final requirements upfront from a fresh start (upfront development: one assignment with normal agent iteration). Both workflows should target equivalent final functionality/security contracts. Budgets and comparison timing remain open; implementation authorization is unchanged.

### Session continuity confirmed

Each incremental step starts a fresh Codex session with the sequence's retained code/project files and requirements revealed so far, without prior conversation history. The owner prefers this as representative of their intended development workflow; this preference is not a verified claim about industry-wide practice. Agent-authored project notes persist; external session memory and prior conversations do not. Independent evaluator results are confirmed hidden; local security-review feedback is a separate intervention.

### Review feedback and independent scoring

Owner confirms that independent evaluation stays hidden and wants to investigate how local security-review feedback steers the development agent. Distinguish the intervention reviewer, which supplies feedback, from the hidden evaluator, which scores the artifacts. Review is confirmed at the submission boundary: the owner envisions automatic agent hooks before PR creation, with feedback and bounded repair before pipeline controls. Exact trigger and reviewer remain open; this is a research condition, not a production integration commitment.

### Efficiency requirements confirmed

Collect at least elapsed time and token consumption for every intervention, including reviewer and repair overhead, to assess efficiency and monetary tradeoffs alongside security/functionality. Reviewer execution as a separate agent/session or subagent is acceptable if hook invocation and findings delivery are supported. Exact implementation and budget fairness remain open.

### Practical budget comparison confirmed

Allow measured additional local-review and repair resources; compare the complete workflow cost against other conditions, with separate development/review/repair accounting. Initial development may itself cost more or less under different context; this is an empirical question. Total overhead includes those differences. This does not authorize paid experiments or remove the generic extra-review control needed for attribution. Exact limits remain open.

### Review-cycle limit confirmed

The local-review condition uses one review pass followed by one bounded repair phase per development step. It does not repeat reviews until clean. Exact repair limits remain open; independent pre/post scoring remains hidden.

### Continuation after application failures confirmed

Functional/security failures do not stop an application sequence. Later steps inherit the generated code without hidden evaluator feedback or clean reference replacements. Retain failure history even if later changes recover. Infrastructure failures and hard-budget policies remain separate open decisions.

### Project-file persistence confirmed

Retain all agent-authored project files, including notes and development instructions, between fresh step sessions and in checkpoint snapshots. Exclude previous conversation logs, external session memory and hidden evaluator materials. The owner chooses this to approximate their intended development environment; representativeness is a study assumption, not an established empirical finding. Security observations may persist through notes, forming part of an intervention's downstream effect.

### Baseline-only pilot and phased interventions confirmed

Begin with a baseline ordinary-development pilot to qualify experiment mechanics. Add intervention conditions in later phases: examples include generic security guidance, skills, review/repair and threat-modeling specifications. The owner's list is a roadmap, not an agreed ordering or commitment to implement every condition initially. Fine-tuned models remain a possible later research direction, with training deferred and requiring a separate dataset/evaluation/resource decision. No comparative hypothesis is prioritized by the pilot. Baseline excludes added security guidance, skills, review and behavioral hooks; precise normal harness configuration and pilot size remain open.

### Complete baseline workflow required

The baseline pilot must provide the scaffolding needed to deliver tasks, execute Codex, preserve outputs, evaluate functionality/security independently, and monitor time, tokens and host-side memory. The architecture and tasks still require alignment/spec approval. No intervention is needed to qualify this complete path.

### Initial full-stack application set confirmed

Owner selected five initial benchmark applications with both frontend and backend, each evolved through a sequence. This supersedes the backend-only/single-application recommendation. The purpose includes observing cross-layer security failures and frontend-only controls. Partial risk overlap across application contexts is confirmed; application themes are confirmed in `docs/BENCHMARK_APPLICATIONS.md`, while feature scope and risk matrix remain open; application counts alone do not establish broad generalization.

### Risk redundancy and initial run count clarified

Owner means redundancy of risk opportunities across functionalities, within and across benchmark applications, so one correctly implemented feature does not stand in for every occurrence of a risk. Initially run each application sequence once; identical-sequence repeats are deferred. This qualifies mechanics and observes concrete failures but does not quantify within-task stochastic variation. Five themes are confirmed in `docs/BENCHMARK_APPLICATIONS.md`; exact opportunities and sequence steps remain open.

### Sequence length confirmed

Owner selected ten steps per application: one initial build and nine subsequent requests. Five application sequences run once produce 50 development sessions/checkpoints. Their dependence within applications remains unchanged. Exact requests, budgets and evaluator scope remain open; this sizing decision does not authorize execution.

### Language diversity reopened

Owner reopened the common-stack policy to consider Python, Go, Node.js, PHP, C# and Java. Owner clarified that different applications use different language stacks, without matched cross-language replicas. Exact subset and assignment remain open. This is ecosystem coverage, not an isolated language-comparison experiment. Node.js is a runtime, with JavaScript/TypeScript as candidate languages. No language-effect claim should ignore framework/runtime/task confounding.

### Backend assignments confirmed

Owner accepted Python for the document portal, PHP for the support desk, C#/.NET for the expense manager, Go for the integration dashboard and TypeScript/Node.js for the marketplace. Java is deferred. Frontend, backend frameworks and databases remain open; application/stack effects remain bundled.

### Frontend policy confirmed

Application-specific frontend approaches are accepted. The owner clarified that creativity belongs to the benchmark author implementing future benchmark-definition tickets. The author defines scenarios, frontend choices, task contracts and hidden evaluation; the evaluated agent builds from released requests. Exact framework choices, initial workspaces and evaluated-agent architectural freedom remain open.

### Developer-request simulation and initial state confirmed

The benchmark simulates tasks arriving during a developer's project. Start each application sequence from an empty project with a prepared runtime/toolchain, first request and selected technology constraints. Later threat-modeling experiments may add instructions before implementation; exact treatment and delivery remain deferred, with the baseline unchanged.

### Mixed task sequence confirmed

Owner accepted feature additions, requirement changes, predefined bug-fix requests and refactoring within each application sequence. The goal is evolving developer work rather than ten unrelated additions. Exact requests remain open; scenario bug reports are independent of hidden evaluation and do not presume a specific defect exists in generated code.

### Request completeness varies

Owner wants realistic variation in detail, from well-described tasks to hurried requests omitting security context. Hidden security evaluation may therefore assess expectations not fully stated in task context. Distinguish security expectations from explicit functional/specification compliance, record assumptions and avoid overclaiming why an agent failed. The information contribution of later interventions must remain visible in the analysis.

### Fixed base requests confirmed

The benchmark author chooses request detail levels before execution and keeps ordinary task requests identical across conditions. Interventions are explicit versioned additions or preparation stages. Pilot revisions create new task versions; freeze the eventual comparison protocol before interpreting effects.

### Initial access confirmed

The baseline pilot uses the owner's existing Codex subscription. No paid API experiments are approved. Record time/tokens and distinguish estimated API-equivalent costs from actual subscription spending. Model and reasoning settings remain open.

### Model selection deliberately deferred

Owner currently uses GPT-6.1-Sol/default but does not select it as the study configuration yet. Choose and record exact settings at pilot execution. Current alignment priority is the complete research system/scaffolding, benchmark application definitions and independent final evaluation, not model selection. This does not remove the existing alignment/spec gate before implementation.

### Independent evaluator role confirmed

The evaluator agent runs hidden functional/security checks and investigates additional issues. Executable checks provide primary scores; agent-discovered vulnerabilities require separate reproducible validation and reporting. The evaluator remains distinct from local-review feedback and never supplies results to development agents.

### Initial research platform interface confirmed

Owner accepted a command-line platform with local structured artifacts and readable reports, supporting selection, execution/resumption, checkpoint evaluation and resource inspection. No web dashboard is required initially. Resume semantics and technical implementation remain open.

### Checkpoint-boundary resume confirmed

Resume completed sequences at the next step in a fresh session. Preserve interrupted partial attempts and their resource usage; retries are explicit and start from the previous completed checkpoint. Initial scaffolding need not recover an interrupted agent session.

### Realistic agent workflow and simplicity

Owner prioritizes ordinary developer-agent behavior and experimentation with security solutions, later harnesses/models. Do not force offline development or turn routine scaffolding details into research dimensions. Keep normal development tools/access, passive measurement and hidden evaluation boundaries. Consolidated scope is in the draft `docs/BASELINE_PILOT_SPEC.md`, pending review.
