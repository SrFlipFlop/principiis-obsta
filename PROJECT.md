# Project guide

## What we test

We test interventions that aim to improve how securely coding agents write code. The baseline is ordinary Codex development with no added security guidance, skills, review or hooks. Interventions come later and are compared against it. Terms are defined in [GLOSSARY.md](GLOSSARY.md) and decisions with lasting trade-offs are in [docs/adr/](docs/adr/).

## The loop

1. Pick a **benchmark application** and a **condition** (currently only `baseline`).
2. **Develop step N**: a fresh Codex session in a restricted container gets the current request plus earlier ones, and the project files from step N−1. It never sees future requests or hidden checks.
3. **Snapshot**: the controller saves the workspace as an immutable snapshot, with logs and resource measurements.
4. **Evaluate step N**: hidden functional and security checks run against the snapshot in a separate restricted container. The results are never shown to the developer agent.
5. Move on to step N+1, even after a failed check.
6. **Compare conditions**: do this for each condition on the same requests, then compare the per-step results.

## Kept from the approved baseline spec

- Five applications with ten steps each (an initial build plus nine requests): document portal (Python), customer-support desk (PHP), team expense manager (C#/.NET), workflow dashboard (Go) and online marketplace (TypeScript/Node.js). See the [application catalog](docs/BENCHMARK_APPLICATIONS.md) and `benchmarks/<application>/`.
- Each step starts from an empty project or the previous snapshot. One request is revealed at a time and the requests stay the same across conditions.
- Each step gets a fresh session: it keeps project files and agent-written notes, but not earlier conversations.
- **Primary outcome:** a step passes only if its functional checks AND its security checks pass. Unassessable outcomes are reported, never counted as passes.
- The evaluator agent's findings are secondary evidence. They need reproducible proof and never change primary scores.
- At most 3 explicit retries per step, and every attempt is kept.
- Evaluator changes get a new version, and the affected snapshots are rescored consistently.
- Elapsed time, reported tokens and local memory are recorded. Unavailable values are recorded as unknown. Subscription use is kept separate from API-equivalent estimates.
- Each application gets one run. Checkpoints in a run depend on each other, so the results support no reliability or efficacy claim.

## How to run

Follow the [baseline command sequence](README.md#baseline-command-sequence): `init`, then `develop` and `evaluate` once per step, then `report`. The engineering docs cover the [development commands](docs/engineering/MVP_DEVELOPMENT_CLI.md), [evaluation commands](docs/engineering/MVP_EVALUATION_CLI.md), the [development runtime](docs/engineering/DEVELOPMENT_RUNTIME.md) and [restricted evaluation](docs/RESTRICTED_EVALUATION.md).

## Where hidden material lives

Hidden checks, evaluator bundles, release manifests and private evidence live in the git-ignored `private/` directory of the operator's checkout. Runs are stored under `$PRINCIPIIS_RUNS_ROOT`, outside the checkout. Public `benchmarks/` packages contain only the developer-visible requests and design notes. Keep the research checkout, and any directory with `AGENTS.md` or researcher config in its ancestors, out of development workspaces.

## Benchmark packages

An application is data, not code: `benchmarks/<app>/package.json` lists `id`, `version`, `steps`, `qualified_through`, `private_bundle_sha256` and a `files` map of SHA-256 digests covering `requests/01.txt`…. `qualified_through` is the last step whose evaluator passed its controls ([ADR 0002](docs/adr/0002-control-tests-qualify-evaluator-versions.md)); `init --steps` accepts 1 to that number and defaults to it. The private evaluator declaration, whose digest the package pins, names each step's contract and app command, the evaluator images and `evaluator_command` (declarations without it run the Node oracle, `node /oracle/check.cjs`). `principiis/benchmark.py` is the only loader; `python3 -m principiis.benchmark release --application APP --step N --output DIR` writes the cumulative request text a developer sees at step N.

## Out of scope right now

- Security interventions (guidance, skills, review/repair hooks, threat models). The planned first one is the [plan–implement–verify skill](docs/DEVELOPMENT_SKILL_CONDITION.md).
- Repeated runs, the upfront-development comparison, other harnesses or models, Java, and fine-tuning.
- Dashboards, databases and general frameworks for the controller.

Research background is in [docs/research/](docs/research/README.md) (charter, protocol, related work, literature). It is useful for the paper but not required reading. Earlier specs, plans and reviews are in [docs/archive/](docs/archive/). The benchmark request-authoring reviews stay in `docs/reviews/`, because the content-hashed benchmark packages link to them.

## Status

Status lives in GitHub issues. Read the current issue body, comments and blockers before starting work.

## Decisions log

- 2026-11-14: Baseline scope approved: five apps with the backends above, ten steps each, one run per app, Java deferred.
- 2026-11-14: Triage label names approved (see [triage labels](docs/agents/triage-labels.md)).
- 2026-11-15: Requests carry ordinary business policy but no researcher-added security guidance. Hidden security expectations apply whether or not a request states them ([ADR 0001](docs/adr/0001-separate-baseline-requests-from-security-expectations.md)).
- 2026-11-15: The developer and the evaluator both use ordinary Codex subscription access with the harness's default model and reasoning settings. Effective values are recorded, or "unknown".
- 2026-11-15: No step or sequence time limits. Retries are capped at 3 per step.
- 2026-11-15: Development and evaluation are triggered manually and separately at each checkpoint.
- 2026-11-20: The owner chose a custom plan–implement–verify skill as the first intervention direction.
- 2026-11-21: The document portal's requests 1–3 and their hidden evaluator were qualified model-free. Requests 4–10 are not qualified yet.
- 2026-11-24: The #59 three-step portal audit closed. Its closing comment cites `docs/reviews/ISSUE_59_THREE_STEP_AUDIT_20261124.md`, but that report was never committed, so the comment itself is the record.
- 2026-11-25: #44 accepted: the first-three evaluator was applied to retained Codex checkpoints ([record](docs/archive/reviews/ISSUE_44_ACCEPTANCE_20261125.md)).
- 2026-11-26: Simplification (#62): agents follow only the four hard rules in [AGENTS.md](AGENTS.md). Control tests (safe, violating, reject-all, alternative-valid) decide whether an evaluator version is usable. The owner approves milestones, not bundle hashes ([ADR 0002](docs/adr/0002-control-tests-qualify-evaluator-versions.md)).
