> Alignment completed: owner approved `docs/BASELINE_PILOT_SPEC.md` on 2026-11-14. Next prepare small baseline implementation/benchmark-author tickets using the available workflow. The initial stop gate below is historical; no new grill is needed for routine engineering choices. Paid experiments remain unauthorized.

# Matt Pocock workflow — local compatibility and alignment gate

Checked 2026-11-14. [Upstream README](https://github.com/mattpocock/skills), Installation and workflow guidance, was inspected. It offers Codex plugin or editable-file installation and warns against duplicate installs. The local session already exposes Matt's editable skills under `/home/srflipflop/.agents/skills/`; no installation is needed here. CLI 0.169.0 supports plugins, but the local catalog lists Matt's plugin as not installed. Do not install another copy merely to match upstream naming.

## Installed workflow

The installed `/setup-matt-pocock-skills` and `/grill-with-docs` use `CONTEXT.md` and `docs/adr/`. Installed planning skills include `/to-prd`, `/to-issues` and `/tdd`; current upstream names `/to-spec`, `/to-tickets`, `/implement`, `/code-review` and `/retro` are not all exposed here. Do not promise unavailable commands or unverified dependencies. Use the loaded skill's instructions; deliberately reconcile names if upgrading later.

Owner selected GitHub Issues, standard triage role names and single-context layout. The previously displayed setup draft is now applied: see `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md` and `docs/agents/domain.md`. The reviewed text is retained in `docs/agents/SETUP_DRAFT.md`. No remote issues or labels are created by setup.

## Next: owner-led alignment

Invoke `/grill-with-docs` directly in the main conversation. It interviews one question at a time, answers repository-verifiable questions itself, and creates glossary terms/ADRs only when agreed and warranted. Do not prepopulate glossary or ADRs with this setup pass's proposals.

Suggested opening:

> Grill me on the research objectives and scientific methodology before implementation. Read START_HERE, the four research reports, synthesis, charter, protocol and open decisions. Ask one question at a time with a recommendation. Challenge novelty, information equivalence, oracle validity, task population, budgets, system/model comparability and the value of negative results. Record agreed vocabulary in CONTEXT.md and only consequential hard-to-reverse decisions as ADRs. Finish with agreed scope and remaining uncertainties.

After alignment, create and review a specification capturing all material decisions; a glossary is not a spec. Use available PRD/issue skills where suitable, then small test-driven slices and independent review. Do not create implementation tickets before research scope is agreed. Development-workflow skills are not benchmark interventions.

**Stop gate:** this setup ends before the grill. No benchmark runner/task/intervention implementation, experiment, paid API workload, publication claim or architectural commitment is authorized by completing these documents.
