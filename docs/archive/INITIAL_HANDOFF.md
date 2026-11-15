> Historical handoff and alignment record, retained on 2026-11-15. For current instructions use [START_HERE](../START_HERE.md) and the [development workflow](../agents/workflow.md). References to `CONTEXT.md` describe the former glossary name; current terminology is in [GLOSSARY.md](../../GLOSSARY.md).

> Current status: the owner completed `/grill-with-docs` and approved [baseline pilot specification](../BASELINE_PILOT_SPEC.md) on 2026-11-14. Proceed to baseline implementation planning under that scope. Earlier setup/alignment instructions below are historical. No pilot has been executed; model/settings and run limits remain deferred.

# Codex handoff — read first

Project: **Principiis Obsta** (Latin: “resist at the beginning”). Working slug: `principiis-obsta`.

## What the owner wants

The owner works in AppSec/OffSec and is interested in the evolution of secure software engineering as coding agents become responsible for implementation. The original intuition was to move prevention farther left than CI/CD: teach an agent what security awareness used to teach people; give it local verification; and, most promisingly, include security risks and controls in specifications **before it writes code**.

They intend to run an independent, small, reproducible research project, release the code and write a blog or paper. They have access to Codex and Claude, and can run some local models using LM Studio or Ollama. No paid multi-model workload has been authorized. They want Codex to spawn research subagents, not assume this handoff is the end of literature research.

## Original four intervention families (preserve all)

1. **Security knowledge**: generic secure-coding skills, task-conditional skills; eventually RAG or a graph knowledge base if evidence justifies it.
2. **Local feedback**: hooks in the coding environment, SAST and/or agent review, findings returned to the writer for repair.
3. **Curated design context**: threat modeling and explicit requirements integrated with specification-driven development; distinguish additional facts from the structure of threat models.
4. **Specialized small models**: eventually fine-tuned or adapted models for risk recognition, context selection, or secure development; postpone training until a benchmark and dataset exist.

A fifth possible synthesis is **adaptive security context**: activate targeted guidance, requirements, and tests only where relevant. It is a hypothesis to explore later.

## Sequence requested by the owner

1. Inspect/initialize the local repository safely and document what already exists.
2. Read and preserve the project's background in this starter pack.
3. Delegate **four independent research tracks** to Codex subagents. Consolidate evidence; correct stale assumptions and explicitly label unresolved questions.
4. Set up the minimal research-doc structure and agent instructions. Avoid implementing benchmark functionality yet.
5. Install/configure Matt Pocock's skills for **Codex** (with the owner's approval); use `/setup-matt-pocock-skills` as appropriate.
6. **Stop and ask the owner to start `/grill-with-docs`** for objectives, glossary and decision alignment. Only after that session and a reviewed spec/tickets should coding begin.

If an existing Git repo is present, do not overwrite uncommitted work or reset history. Do not push or create a remote unless asked.

## What to report at the stop gate

- The repo structure and status; exact actions performed and validation results.
- Research tracks completed / blocked, references verified, contradictions and gaps.
- Short list of decisions to resolve in `/grill-with-docs` (from `docs/OPEN_DECISIONS.md`).
- Confirmation that **no experiments or benchmark implementations** have started.

## Index

- `RESEARCH_CHARTER.md` — purpose, scientific questions, scope and intended outcomes.
- `EXPERIMENT_PROTOCOL.md` — candidate treatment arms, controls, scoring, isolation, pilot.
- `RELATED_WORK.md` — literature and tool starting points that need refreshed verification.
- `RESEARCH_ASSIGNMENTS.md` — research subagent briefs and evidence format.
- `OPEN_DECISIONS.md` — deliberately unanswered owner-level decisions.
- `MATT_POCOCK_WORKFLOW.md` — setup and next-phase workflow.

## Completed research refresh — 2026-11-14

Read [research index](../research/README.md), all four reports, [synthesis](../research/05_SYNTHESIS.md), and [repository audit](../REPOSITORY_AUDIT.md) before the next alignment session. These qualify the starter assumptions; none is an approved experimental specification. Owner README was preserved; starter README is archived as `STARTER_README.md`. The existing repository license is MIT. Follow the installed-skill compatibility notes in `MATT_POCOCK_WORKFLOW.md`.

## Application scope agreed during alignment

The five full-stack themes are recorded in [benchmark application catalog](../BENCHMARK_APPLICATIONS.md). Each application has ten steps. Exact requests and evaluation contracts are benchmark-author work within the approved spec.

## Alignment consolidation

[Approved baseline pilot specification](../BASELINE_PILOT_SPEC.md) consolidates the owner's decisions and supersedes earlier multi-arm pilot/shared-stack/offline-development proposals. Owner approved this scope; implementation tickets are next, while actual pilot execution awaits deferred settings/limits.

## Published implementation plan

The owner-approved [19-issue breakdown](../planning/BASELINE_ISSUE_BREAKDOWN.md) is published on GitHub. Start with [issue #1](https://github.com/SrFlipFlop/principiis-obsta/issues/1); respect blockers and HITL reviews. No benchmark implementation or pilot run occurred during issue publication.
