# Principiis Obsta — start here

Principiis Obsta studies security interventions in coding-agent development. The current work implements and qualifies the baseline path: ordinary Codex development, retained checkpoints, independent functional/security evaluation and resource accounting. Later interventions remain outside this phase.

## Read before working

1. [Approved baseline specification](BASELINE_PILOT_SPEC.md) — scope and owner decisions, including the 2026-11-15 execution settings. Technical qualification and separate pilot launch approval remain required; paid API runs remain unauthorized.
2. [Glossary](../GLOSSARY.md) and relevant [ADRs](adr/) — agreed language and consequential rationale. The glossary was renamed from `CONTEXT.md` on 2026-11-15; definitions are preserved.
3. [Open decisions](OPEN_DECISIONS.md) — unresolved authoring, qualification and later-phase work.
4. The current GitHub issue body, comments and blockers — actual work status. The [original issue breakdown](planning/BASELINE_ISSUE_BREAKDOWN.md) and its JSON export record the 2026-11-14 publication, rather than a live queue. See the [issue tracker instructions](agents/issue-tracker.md).

The specification governs approved scope. The glossary defines terms, ADRs explain decisions, and engineering documents describe implemented behavior. Research findings and proposals remain distinct from decisions. An old setup gate or a completed ticket's historical wording does not override current scope.

## Choose the relevant path

| Work | Start with |
| --- | --- |
| Alignment, planning, implementation or review | [Development workflow](agents/workflow.md) |
| Portal development rehearsal commands (#40–#42) | [MVP development CLI](engineering/MVP_DEVELOPMENT_CLI.md) and [runtime preparation](engineering/DEVELOPMENT_RUNTIME.md) |
| Portal evaluation integration (#43–#45) | [MVP evaluation CLI](engineering/MVP_EVALUATION_CLI.md) and [implementation/prerequisite record](reviews/MVP_2_IMPLEMENTATION.md); qualified #8/#9 packages and live acceptance remain required |
| Live milestone-1 evidence and owner acceptance | [Requests 2–3, interruption/retry and reconciled exports](reviews/ISSUES_41_42_LIVE_QUALIFICATION_20261117.md) |
| Manual checkpoint operation | [Manual workflow](MANUAL_CHECKPOINT_WORKFLOW.md) and [HITL issue #38](https://github.com/SrFlipFlop/principiis-obsta/issues/38) |
| Architecture and proposed improvements | [Architecture review](reviews/ARCHITECTURE_REVIEW.md) |
| Checkpoint/executor contracts | [Checkpoint CLI](engineering/CHECKPOINT_CLI.md) |
| Suite selection and reporting | [Suite CLI](engineering/SUITE_CLI.md) |
| Restricted browser/backend execution | [Restricted evaluation](RESTRICTED_EVALUATION.md) |
| Supplemental evaluator findings | [Independent investigation](engineering/INDEPENDENT_INVESTIGATION.md) |
| Benchmark authoring | [Application catalog](BENCHMARK_APPLICATIONS.md), then the relevant `benchmarks/<application>/BENCHMARK_DESIGN.md` and package metadata |
| Research or methodology changes | [Charter](RESEARCH_CHARTER.md), [protocol](EXPERIMENT_PROTOCOL.md), [research index](research/README.md) and [synthesis](research/05_SYNTHESIS.md) |

For the baseline, manually trigger development and evaluation separately at each checkpoint. Older automatic sequence/suite commands are compatibility and engineering-fixture paths; their behavior is documented, but they do not select the current pilot workflow. Qualification of a tiny fixture does not qualify an application's evaluator. Consult the current work item before assuming a draft request package is executable.

## Repository map

| Path | Responsibility |
| --- | --- |
| `principiis/` | Local controller, execution adapters, checkpoint preservation, evaluation and reports |
| `tests/` | Controller behavior through local executable fixtures; real Docker/browser qualification is opt-in |
| `benchmarks/` | Versioned authoring packages and released task contracts; deliver only the permitted request content to evaluated agents |
| `fixtures/` | Harmless engineering controls and restricted-evaluation preparation |
| `docs/engineering/`, `docs/reviews/` | Implemented contracts and dated review evidence |
| `docs/research/`, `docs/planning/` | Dated research findings and original planning records |
| Ignored `private/`, `artifacts/` | Operator-owned hidden evaluation material and local evidence; keep outside development contexts and public Git |

Run routine controller checks from this checkout with `python3 -m unittest discover -s tests -v`. Prepared container qualification requires separate environment configuration; preserve skips and failures in the verification record.

The [initial handoff](archive/INITIAL_HANDOFF.md), [skill setup record](MATT_POCOCK_WORKFLOW.md), [applied setup draft](agents/SETUP_DRAFT.md), [starter README](STARTER_README.md) and [bootstrap prompt](BOOTSTRAP_PROMPT.md) retain provenance. Their setup instructions describe the original phase. The owner's motivation remains in the root README. The repository license is MIT.
