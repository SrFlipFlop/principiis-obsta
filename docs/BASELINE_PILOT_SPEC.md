# Baseline pilot specification — approved

Status: reviewed and approved by the owner on 2026-11-14 after `/grill-with-docs`. Baseline scaffolding, benchmark authoring and independent evaluation are approved in scope. Actual pilot execution still requires qualified machinery and separate launch approval; execution settings were subsequently selected on 2026-11-15 below. Paid API experiments remain unauthorized. Routine engineering choices below are proposals, not experimental conclusions. This document takes precedence over superseded pilot recommendations in the research notes; terminology is in [GLOSSARY.md](../GLOSSARY.md).

## Purpose and scope

Create the complete, minimal research scaffolding for experimenting with security interventions during realistic coding-agent development. First qualify it with ordinary Codex development only. Use the owner's existing subscription; choose the actual model/reasoning settings at execution time. No paid API runs are approved.

The evaluated agent uses ordinary tools, dependency installation and documentation/network access under its normal configured permissions. Do not force offline development, replace its workflow with a custom harness, or supply researcher-added security guidance, skills, review or behavioral hooks in the baseline. Keep task context separate from researcher instructions and hidden materials. Record the normal setup and keep it consistent across compared conditions. Passive measurement must not steer the agent.

## Benchmark suite

| Application | Backend |
| --- | --- |
| Document portal | Python |
| Customer-support desk | PHP |
| Team expense manager | C#/.NET |
| Integration/workflow dashboard | Go |
| Online marketplace | TypeScript/Node.js |

All five are full-stack, with application-specific frontend approaches selected by the benchmark author. Java is deferred. No cross-language replicas are required. Each application has ten steps: initial build plus nine requests. One baseline sequence run per application gives 50 development sessions/checkpoints; repeated runs are deferred. Risk redundancy means multiple opportunities across functionalities, not repeated generations or independent statistical samples.

The benchmark author defines and versions all ten requests, minimal external API contracts, expected functionality and hidden evaluation before comparison. Mix features, changed requirements, predefined bug reports and refactoring, with varying detail levels. Preserve identical base requests across conditions. Record whether each security expectation is stated, implied or absent; document evaluator assumptions and ambiguous policies. Bug reports must not be derived from the current run's hidden results or presume a specific defect exists.

Start from an empty project with runtime/toolchain available. Reveal one request at a time; keep previous requirements available and future requests hidden. Each step uses a fresh Codex session. Retain the run's project files and agent-written notes, excluding prior conversation history and external session memory. Do not inject reference implementations. Continue after candidate functional/security failures without revealing evaluation results.

## Command-line workflow

The platform must select applications/conditions, deliver step instructions, invoke ordinary Codex, preserve outputs, evaluate snapshots, report results and resume at completed checkpoints. Store structured local artifacts and readable reports; no initial web dashboard.

At each completed step, preserve an immutable snapshot or equivalent recoverable state, task/condition versions, resolved execution configuration, logs, exit status and resource measurements. Keep hidden evaluator artifacts outside development contexts. Interrupted attempts retain partial files/logs/costs; an explicit retry begins at the last completed checkpoint with a separate attempt record. No initial live-session recovery requirement.

Implementation proposal: use a small controller, declarative task files and filesystem artifacts. Select the controller language, commands, directories and serialization format during specification/ticket refinement; do not build a universal framework, plugin system, database service or dashboard without demonstrated need.

## Independent evaluation

Predefined executable functional and security checks supply primary checkpoint scores: required functionality AND tested security properties pass. Independently test browser behavior and backend access so UI-only controls do not count as backend protection. Report failures and unassessable outcomes explicitly. Checkpoints within an application are dependent; this pilot does not estimate efficacy or stochastic failure probabilities.

An independent evaluator agent runs checks and investigates additional vulnerabilities. Supplementary findings require reproducible evidence and verified/rejected/unresolved status; finding counts are not ground truth. Keep evaluator tests, notes, outputs and findings hidden from development. Do not silently revise scores when new issues are discovered: version evaluator changes and rescore affected artifacts consistently.

Run generated applications/checks in disposable restricted environments without production secrets. Simulate external integrations with controlled fixtures for repeatable evaluation. This evaluation boundary does not impose an offline policy on the coding agent. Qualify the oracle with safe, property-violating and broken/reject-all controls, alternative valid implementations and flakiness checks before treating scores as reliable. Exact checks, fixtures and ambiguous-policy adjudication belong in the benchmark-author tickets.

## Resource and process evidence

Record elapsed time, reported token usage and local agent/tool memory, with stated measurement scope. Hosted model RAM is not observable. Separate development, later intervention stages and independent evaluation costs. Preserve incomplete attempts and avoid duplicate usage accounting. Report unavailable values as unknown, distinguish actual subscription spending from API-equivalent estimates, and label the pricing assumptions of any estimate.

Collect exposed events, commands, edits and summaries without demanding extra explanations. These are exploratory process evidence, not private chain of thought or proof of causality.

## Later phases

Add conditions incrementally: generic guidance, skills, local security review/repair, threat-modeling specifications and other justified ideas. Fine-tuning remains deferred. Exact order and delivery mechanisms are not settled.

The agreed review concept is automatic review before submission, preferably via supported hooks, using a separate reviewer if feasible, followed by one bounded repair phase without automatic re-review. Preserve initial/final snapshots and account for all review/repair costs. Permit additional measured resources and retain a comparable general-review control when interpreting security-specific benefits. Hidden evaluation never feeds this reviewer.

Later compare incremental development with a fresh upfront-development run receiving all final requirements and normal agent iteration. This compares whole workflows, not code erosion alone. Additional harnesses/models come after the initial system.

## Readiness and remaining decisions

Scaffolding is ready when the full baseline path can deliver requests, run ordinary Codex, retain correct state, hide future/evaluator content, preserve artifacts and failures, resume at checkpoints, evaluate browser/backend behavior and report resource use. Verify these properties before scheduling the full 50-step pilot. Passing the pilot does not require every generated application to be secure or functional.

Remaining authoring work: exact ten-step sequences, application framework/database choices, browser/API contracts, security properties and evaluator controls. Execution settings and retry limits were selected on 2026-11-15 below; interruption classification and qualification remain implementation work. Implementation details can be resolved with simple documented choices; they need not become new research dimensions.

Implementation plan: the owner-approved breakdown is published as GitHub issues #1–#19, linked from the local planning document. Begin with issue #1 and respect dependencies. No benchmark implementation or experiment was performed during alignment or issue publication.

## Owner clarification — 2026-11-15

Issue #8 alignment clarified the existing baseline boundary: requests vary in detail and technical prescription, retain ordinary business policy and omit researcher-added secure-development guidance. Hidden security properties can apply even when absent from requests; absence is a visibility label, not an exemption from security evaluation. Compatible third-party dependencies remain the evaluated agent's choice. Minimal integration contracts must accommodate legitimate implementations. These principles supersede the early Fieldwork authoring choices that restricted dependencies and mapped primary security exclusively to supplied rules. See [ADR 0001](adr/0001-separate-baseline-requests-from-security-expectations.md). Concrete revised request/rubric intent was subsequently approved as recorded below; oracle qualification remains pending. No pilot launch or paid run is authorized.

## Owner execution decisions — 2026-11-15

The owner selected ordinary Codex subscription access for both developer and evaluator, using the harness default model and reasoning settings. Record effective model/reasoning values when exposed; otherwise record unknown. Apply no step or sequence time limits, and measure elapsed time and reported tokens. Allow at most three explicit retries per step, preserving every attempt. Development and evaluation must be separately triggered manually for each checkpoint; do not automatically execute the whole sequence. These decisions supersede the earlier deferral of settings, time limits and retry policy and require corresponding controller support.

The owner also approved issue #8's concrete revised request/rubric intent. Technical oracle and runtime qualification remain pending; a subsequent safe-control trial exposed a clock regression. Intent approval does not complete #8 or authorize a pilot launch or paid calls.
