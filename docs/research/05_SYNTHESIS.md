# Research synthesis and alignment gate

2026-11-14. Status: research complete for this setup pass; objectives, architecture and experimental scope remain unapproved. Evidence is in the four [research reports](README.md); local provenance is in [repository audit](../archive/REPOSITORY_AUDIT.md).

## What the evidence changes

**Novelty:** generic guidance, selected security context, supplied requirements, planning and scan/review repair all have direct prior work. [Literature report](01_LITERATURE_NOVELTY.md) maps exact comparisons and source sections. Joint functionality/security scoring is established methodology. We should initially frame this as an intervention study or replication, rather than promise a new benchmark or novel preventive technique.

**Benchmark:** [reuse review](02_BENCHMARK_REUSE.md) finds existing evaluators worth inspecting before custom construction. BaxBench offers application generation; SusVibes offers repository modifications. These are different units and should not be casually pooled. Counts depend on versions and scenario/framework families. DualGauge is partly model-judged and its reuse license remains unverified.

**Reliability:** the [evaluation critique](03_EVALUATION_VALIDITY.md) identifies oracle qualification, task sampling and a precise estimand as prerequisites. Three tasks with repeated trials are a mechanics pilot. They do not support broad efficacy or null-effect claims. Reject-everything controls, alternate valid implementations, flakiness checks and independent adjudication are essential.

**Feasibility:** [existing CLIs](04_AGENT_HARNESS_FEASIBILITY.md) appear to provide enough logging/noninteractive control. The uncertain work is curation, equivalent intervention texts and trustworthy evaluation, not a universal runner. Local hardware/account capacity and actual runtime remain unmeasured.

## Ranked candidate contributions — recommendations, not decisions

| Rank | Candidate | Potential contribution | Effort/risk |
| --- | --- | --- | --- |
| 1 | Flat criteria versus threat-model representation with identical security facts | Separates information from structure; novelty still requires focused overlap audit | Medium; equivalence may be impossible without narrowing the treatment |
| 2 | Reproducible replication of requirements/functionality tradeoffs | Useful bounded result even if not a new technique; supports positive or negative findings | Low-to-medium with qualified reused tasks; oracle underspecification remains central |
| 3 | Prevention versus security repair versus generic extra review | Tests timing while controlling added review opportunity | Higher; compute accounting and initial/final snapshot requirements |
| 4 | Adaptive context or specialized small models | Potential efficiency/generalization question | High; prior overlap, selection errors and hardware/training burden; defer |

## Smallest feasible proposal for the grill (historical recommendation)

> Subsequent alignment selected a baseline-only mechanics pilot, with interventions added in phases. The multi-arm suggestion below is superseded as pilot scope; see the current experiment protocol.

Choose one task unit and one fixed agent/model. Begin with a paper-level audit of matched requirement texts and evaluator contracts. After alignment and an approved spec, qualify a few development tasks and the experimental mechanics. C0/C3/C4 are candidate arms; keep C1 only if it answers the selected question. The starter's 36-run pilot remains an alternative, not a commitment. Select reused versus custom tasks after metadata/license/oracle review. Keep broader statistical claims for a later, independently diverse task set and prespecified analysis.

Preserve all four intervention families in the charter, while deferring local-model comparisons, training, combinations and repair until warranted. No proposal here settles language/framework, container architecture, agent adapter design or sample size.

## Disagreements and remaining uncertainty

- Research tracks independently favor a narrow C3/C4 contrast, but none establishes novelty or proves semantic equivalence is achievable.
- Reuse offers comparability, whereas custom tasks offer control. The best choice depends on whether the owner prioritizes realistic repository changes or a cheap causal pilot.
- Source versions conflict: SusVibes 200 versus 186, early DualGauge 154 versus later 307; commercial forks differ. These are version distinctions, not counts to reconcile by averaging.
- Current upstream workflow differs from installed skills. Use the installed convention with owner confirmation, rather than assume commands/dependencies are available.
- No empirical hardware, cost or evaluator-reliability measurements exist yet. Source documentation is feasibility evidence only.

## Decisions for the next session

1. Primary contribution and acceptable first deliverable, including a null/negative result.
2. One primary contrast and meaning of threat modeling: representation, extra information or discovery.
3. Task unit/population and reuse/custom strategy, including public/held-out split.
4. Requirements provenance and functional contract when stricter security rejects inputs.
5. One fixed agent/model and credential mode; confirm hardware and no-paid budget.
6. Allowed resources, stopping/retry rules and minimum meaningful benefit.
7. Oracle qualification, independent adjudicator and treatment-equivalence reviewer.
8. Claim limits, task diversity, uncertainty/multiplicity and preregistration.
9. Release/provenance policy and confirmation of existing MIT license for our own work.

Proceed with owner-led `/grill-with-docs`, one question at a time. Resolve vocabulary and scope, then review a spec before tickets or implementation. No benchmark runner, tasks, interventions, paid calls or experiments were implemented/run in this setup pass.
