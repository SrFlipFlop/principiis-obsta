# Remaining decisions and authoring work

Owner completed `/grill-with-docs` and approved [baseline pilot specification](BASELINE_PILOT_SPEC.md) on 2026-11-14. Agreed vocabulary is in [GLOSSARY.md](../GLOSSARY.md); the five themes/backend assignments are in [application catalog](BENCHMARK_APPLICATIONS.md). Do not reopen accepted scope to settle routine implementation details.

## Agreed baseline scope

- Command-line platform using ordinary Codex development through the owner's subscription; no added security guidance, skills, review or behavioral hooks.
- Five full-stack applications with assigned backend ecosystems, ten developer requests each, one initial run per application. Multiple risk opportunities across functionalities; identical-run repetition deferred.
- Empty starting project with runtime/toolchain available; normal development tools, dependency installation and documentation/network access under configured permissions.
- Incremental disclosure, fresh step sessions, retained project files/notes, no previous conversation or external session memory. Preserve candidate failures and continue; resume at completed checkpoints with explicit retained retries.
- Hidden executable functional/security checks determine primary scoring; an independent evaluator agent investigates additional validated findings. No evaluator feedback to development.
- Local structured artifacts/readable reports and time/token/memory accounting. No initial dashboard or universal framework.

## Resolve during benchmark authoring and ticket refinement

1. The exact ten requests per application, their detail levels, cumulative/changed requirements and risk-opportunity mapping. Fix ordinary requests before comparing conditions.
2. Application-specific frontend/backend frameworks and database choices within the assigned ecosystems; minimal API/browser contracts and startup/reset instructions.
3. Hidden functional/security checks, source/rationale of unstated security expectations, handling of genuinely ambiguous policy, oracle qualification and reproducible fixtures.
4. Evaluator-agent prompt/tools, finding evidence and verified/rejected/unresolved classification; human adjudication for uncertain claims where needed.
5. Simple platform implementation choices: controller language, commands, schemas, storage layout, resource measurement boundaries and interruption classification. Document reasonable decisions rather than treating each as a new research question.

These are work items within approved scope, not blockers requiring a new alignment session for every detail. Avoid copying benchmark answer keys into evaluated contexts.

## Owner execution decisions — 2026-11-15

Developer and evaluator both use ordinary Codex subscription access with harness default model/reasoning. Record effective values when exposed, otherwise unknown. No step or sequence time limits apply; measure elapsed time and reported tokens. At most three explicit retries per step are permitted, preserving all attempts. The owner manually triggers development and evaluation separately at each checkpoint. Controller support must implement these decisions before use.

Issue #8's current `v3-draft1` first three requests completed model-free restricted oracle qualification, owner review and a scoped binding check on 2026-11-21; see [qualification record](reviews/ISSUE_8_V3_TECHNICAL_QUALIFICATION_20261121.md). This supersedes the old clock-regression status as the current technical observation. Requests 4–10 and the full ten-step package remain unqualified for #9; live generated-checkpoint acceptance remains #43–#44 work.

## Deliberately deferred until execution

- Account capacity and any further practical resource decisions. Subscription access does not authorize paid APIs.
- Scheduling the 50-step baseline after the machinery and oracles are qualified. Preserve all failed/incomplete attempts and make no efficacy claim from the pilot.

## Later research phases

- Intervention order and precise artifacts: generic guidance, skills, one-pass review/repair, threat-modeling specs and justified combinations. Threat-model delivery and supplied versus inferred facts remain open.
- Generic-review comparator and cost accounting for review studies; exact hook implementation validated before use.
- Upfront-development comparison, repeated runs, additional harnesses/models, Java and other ecosystem coverage.
- Fine-tuning requires a separately justified dataset, evaluation and resource plan; no training authorized now.
- Broader task sampling, preregistration and uncertainty for efficacy claims; release/holdout policy, artifact sanitization, independent adjudication and publication venue/timeline.

Existing repository license is MIT. Audit third-party task/code/image licenses before reuse. No confidential employer material, credentials or hidden evaluator data should enter public artifacts or issues.
