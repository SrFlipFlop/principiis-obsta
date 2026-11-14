# Parallel subagent research assignments

## Instructions to main Codex agent

Spawn four independent *read-only* research agents (use project-defined agents from `.codex/agents/` when supported, otherwise built-in explorer/research agents with these briefs). Run them concurrently where possible; **wait for all four**. They should read sources, not alter the repository. Consolidate their findings into **separate** markdown notes in `docs/research/`, update `docs/RELATED_WORK.md` with verified corrections, and report disagreements. Do not ask them to produce benchmark task answers or reference fixes.

Each agent should return: **research question; sources with URL/title/date checked; verified statements with exact source locations; methodological consequences; overlap/novelty assessment; limitations; recommended next investigation; open questions.** If unable to access a source, say so—never invent a paper result.

### Agent 1 — `literature_researcher`

Scope: BaxBench, RealSec-bench, DualGauge, SusVibes, Agent Security League; find additional 2025–2026 work comparing security interventions (not just models). Build a table of what has actually been tested, including statistical designs and threats to validity. Flag where the novelty claim must be narrowed.

### Agent 2 — `benchmark_researcher`

Scope: inspect task formats, executable security oracles, licenses, realism, effort to reuse portions of BaxBench/SusVibes/DualGauge. Compare custom three-task pilot vs importing tasks. Propose validation/anti-leakage checks; avoid copying any reference exploit/solution into places evaluated agents can access.

### Agent 3 — `evaluation_critic`

Scope: review scoring validity, LLM reviewer bias/blinding and calibration, severity counts versus verified security invariants, true/false positives, inference budget fairness, repeated-trial design and uncertainty. Act as a skeptical reviewer and propose pre-registration fields / failure rules.

### Agent 4 — `agent_harness_researcher`

Scope: current Codex CLI/Claude Code capabilities and supported noninteractive running/logging; subscription versus API access and usage constraints; LM Studio and Ollama local inference integration; hook portability; how to hold the harness constant for model-only comparisons; isolation and approximate resource overhead. Do not install or authenticate tools as part of research.

## Cross-agent synthesis

After all reports: rank research gaps by potential contribution and effort; distinguish facts from hypotheses; recommend the smallest feasible MVP and 5–10 decisions for the owner. **Stop before implementing.**

## Execution record — 2026-11-14

All four read-only tracks completed and were awaited before cross-track synthesis. The session supports three children plus the parent, so literature/benchmark/evaluation ran concurrently and harness research began at the first free slot. Supplied role instructions were passed through general-agent delegation; this tool exposes no named TOML profile selector. Separate source-backed reports are in [research index](research/README.md); no child edited shared files or produced task solutions.
