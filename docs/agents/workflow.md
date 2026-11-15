# Development workflow

This is the research project's working procedure. Experimental instructions delivered to evaluated agents are separate versioned artifacts. Read [START_HERE](../START_HERE.md), the approved specification and the current issue before choosing a workflow.

## Match the task to the available skill

The primary skill names below were exposed in this session's skill catalog and their local instructions inspected on 2026-11-15; the architecture-review skill was supplied explicitly by the owner. Check the current catalog and read the skill before invoking it; files on disk alone do not establish session availability. This is a local compatibility record, not a claim about the latest upstream release.

| Need | Available skill and role |
| --- | --- |
| Resolve an unsettled design or scope decision | `/grilling` asks the current decision frontier in rounds, then waits for answers; routine implementation does not require renewed alignment |
| Define or sharpen domain language; record consequential rationale | `/domain-modeling` updates `GLOSSARY.md` and, when warranted, `docs/adr/` |
| Compare module shapes and test seams | `/codebase-design`; use `/improve-codebase-architecture` when explicitly supplied or available for an architecture scan |
| Turn agreed context into a new PRD | `/to-prd`; its publication steps apply when that workflow is requested |
| Break an approved plan into work items | `/to-issues`; review the proposed vertical slices before publication |
| Implement a behavior change | `/tdd` for a requested test-first workflow; follow the issue's acceptance criteria and repository engineering preferences |
| Review a branch or changes since a fixed point | `/code-review` reviews documented standards and the originating spec independently |

Legacy `/grill-with-docs` and `/setup-matt-pocock-skills` invocations in approval records describe how setup and alignment happened. Keep those records accurate. The current glossary path and domain procedure are in [domain documentation](domain.md). The earlier [skill setup record](../MATT_POCOCK_WORKFLOW.md) is historical. Do not install duplicate skills or rename commands to match an unverified upstream convention.

## Keep one authority for each kind of information

- **Approved scope:** [baseline specification](../BASELINE_PILOT_SPEC.md). Preserve its descriptive filename and approval history; a naming cleanup does not reopen scientific decisions.
- **Terminology:** root [GLOSSARY.md](../../GLOSSARY.md), with definitions only. This replaces the old `CONTEXT.md` filename without a second glossary or a compatibility copy.
- **Consequential rationale:** sequential `docs/adr/NNNN-slug.md` records. Existing ADR 0001 stays accepted at its current path. Add a record when a real trade-off is hard to reverse and would otherwise surprise a future reader; ordinary reversible cleanup needs no ADR.
- **Work and readiness:** current GitHub issue bodies, comments and blockers. The local issue breakdown and JSON export remain dated publication records. New work items must stay within approved scope or explicitly request a scope decision.
- **Implemented contracts:** engineering and operator docs. Read the manual workflow before baseline execution; legacy automatic orchestration remains explicitly separate.
- **Evidence:** dated research and review reports. State what was observed, how it was checked and what remains a proposal. Older counts and runtime qualification describe their recorded version, rather than today's readiness.

## Complete a small change

Establish the current state and preserve existing local edits. Implement the smallest complete behavior supported by the work item, with meaningful regression evidence for behavioral changes and independent review. Documentation-only changes need link, reference and diff checks rather than tests that repeat the prose.

Report the changed behavior, verification results, failures/skips and remaining limitations. Publication follows the user's authorization and the [issue tracker procedure](issue-tracker.md). Pilot execution, paid calls and experimental scope expansion require their own authorization; a development skill never grants it.
