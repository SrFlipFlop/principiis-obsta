# Repository audit — 2026-11-14

## Verified local state

- Existing Git repository; origin is `git@github.com:SrFlipFlop/principiis-obsta.git`. No initialization, remote changes, commits or pushes performed.
- Initial tracked files: `LICENSE` and `README.md`. README already had uncommitted edits; preserved byte-for-byte during setup. Its broad adoption claims are motivation, not verified empirical evidence; its duplicated sentence remains owner text.
- Existing license: MIT, copyright Ferran Obiols, 2026. License choice is therefore a confirmation question, not a missing file. Imported benchmark artifacts require separate license checks.
- Starter extracted to `/tmp/principiis-obsta-starter-extracted/`; archive SHA-256: `c2d11dea2d9905a26dbfc9761456dfd5d5e2aee881d9b9dc0200ad3aff780aa1`.
- Starter guidance, docs, ignore rules and four agent definitions imported. Starter README retained separately as `docs/STARTER_README.md`; owner README preserved.
- Codex CLI reports `0.169.0`. Local help supports `exec`, plugins, and `--oss --local-provider lmstudio|ollama`. Help inspection makes no model calls.
- Matt Pocock skills are already available under `/home/srflipflop/.agents/skills/`. Local plugin catalog reports the Matt marketplace present but plugin not installed. No second installation attempted. Catalog network refresh failed; this does not prevent using already loaded skill files.

## Inconsistencies requiring correction or alignment

1. Starter workflow describes current upstream `GLOSSARY.md` and `/to-spec` → `/to-tickets` → `/implement`; installed skills use `CONTEXT.md`, `/to-prd`, `/to-issues`, and `/tdd`. Follow the actual installed skill, with explicit naming reconciliation before upgrades.
2. Candidate arms C3 and C4 are equal-information only after a proposition-level audit; threat headings can themselves add information. Treat their equivalence as a design requirement to verify.
3. Three tasks and repeated generations support an engineering pilot, not population-wide inference. Repetition cannot replace task diversity.
4. Passing selected security probes is evidence for those properties only. Do not call it proof that an application is secure.
5. Read-only research agents share project context; future evaluated agents must receive isolated task contexts without these notes or answer keys.
6. Four research tracks are requested concurrently; this session permits three child agents plus the parent. First three run concurrently; fourth starts when a slot opens. Named briefs are used through general delegation because this tool has no named-agent configuration selector.

## Scope boundary

Only documentation and supplied research configuration are prepared. No benchmark runner, task repository, model experiment, authentication, deployment or paid workload is authorized here. The owner-selected GitHub tracker, standard label mapping and single-context layout are configured in `docs/agents/` and linked from `AGENTS.md`. No GitHub resources were changed.
