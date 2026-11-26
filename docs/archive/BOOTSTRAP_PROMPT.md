> Historical starter prompt. Setup research is now recorded in `docs/research/`; follow `docs/START_HERE.md` for current state. Do not repeat completed delegation or install duplicate skills.

# First message to paste into Codex

You are setting up **Principiis Obsta**, a small empirical AppSec research project about preventing vulnerabilities during AI-assisted software development. The checked-in documents in this repository are the complete initial handoff from prior discussions, but they are **proposals**, not an approved specification. Start with `AGENTS.md`, `docs/START_HERE.md`, `docs/RESEARCH_CHARTER.md`, `docs/EXPERIMENT_PROTOCOL.md`, and `docs/OPEN_DECISIONS.md`.

## What to do in this session

1. Inspect the current repo and Git status; initialize Git only if missing and safe. Do not overwrite existing files, add remotes, push, or commit without asking.
2. Summarize what you learned, separating confirmed decisions from proposed ones.
3. Spawn **four read-only research subagents in parallel**: `literature_researcher`, `benchmark_researcher`, `evaluation_critic`, and `agent_harness_researcher`. Project definitions are in `.codex/agents/`; briefs are in `docs/RESEARCH_ASSIGNMENTS.md`. If named agents cannot be loaded, delegate to built-in explorer/general agents with the same tasks. **Wait for all four**. They must cite primary sources, not edit shared files, and flag missing evidence.
4. Consolidate results into distinct, cited docs under `docs/research/`; adjust the related-work map and open-decision backlog. Do not blindly trust prior references or numeric results.
5. Review whether this skeleton needs only a few more research files. Keep `AGENTS.md` concise and linked to authoritative docs. Record any limits in available Codex/Claude/local-model support.
6. Check Matt Pocock's official skills README and help me use the correct Codex installation/setup. Do not duplicate skills. Refer to `docs/MATT_POCOCK_WORKFLOW.md`.
7. Give me a concise synthesis and stop at the **alignment gate**. The next step will be **me invoking `/grill-with-docs`** to agree on objectives, vocabulary, evaluation design and scope. Do not start the benchmark runner, tasks or paid model experiments before that.

Scientific requirements: keep experimental interventions versioned, distinguish model versus agent harness, use independent functional **and** security behavior tests, include a blinded fixed-version LLM reviewer only as supplemental discovery, guard against hidden test leakage and benchmark contamination, compare budget-equivalent review, and record costs/latency/failures. The source of truth is the docs; if something is unclear, label it open rather than silently decide.
