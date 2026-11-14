# Evaluation validity and reliability

Checked 2026-11-14. Independent evaluation-critic track; findings are source-backed, recommendations are proposals. No experiments or oracle qualification performed.

## Primary methodological evidence

| Source and location | Verified finding | Application and limits |
| --- | --- | --- |
| [BaxBench, abstract](https://proceedings.mlr.press/v267/vero25a.html) | Functional tests and executable end-to-end exploits jointly evaluate backends | Established approach; does not validate our future oracle. |
| [Zheng et al., Judging LLM-as-a-Judge v4, §§3.3–3.4, App. D.1](https://arxiv.org/html/2306.05685v4) | Position, verbosity, self-enhancement and reasoning limitations | Blind and calibrate reviewers; dialogue-preference agreement is not security-review accuracy. |
| [Dror et al., ACL 2018, §§3–5, pp. 1390–1391](https://aclanthology.org/P18-1128.pdf) | Common significance procedures assume independent observations; test selection depends on setup | Attempts/tests cannot count as independent task samples. Source does not prescribe a ready-made test for our hierarchy. |
| [Kapoor et al., AI Agents That Matter v1, §§2, 5–6](https://arxiv.org/html/2407.01502v1) | Cost-controlled evaluation, holdouts and reproducibility matter | Measure real resource use and include generic-review comparator. General methodology, not secure-coding efficacy evidence. |
| [Chen et al., code models v2, §3 after Eq. 1, App. A](https://arxiv.org/html/2107.03374v2) | pass@k describes oracle selection among samples | Repeats should estimate single-run success; any-of-three is a different workflow unless a permitted selector finds the successful output. |

## Prioritized design critique — proposals

**Define the estimand.** A candidate is the treatment difference in probability that one budget-bounded development run satisfies every prespecified functional and security property, averaged equally over selected tasks. State whether inference concerns only fixed tasks or a broader population, and justify sampling for the latter.

**Qualify the oracle first.** Require a property-satisfying functional control, functional property-violating controls, a reject-everything/broken control, alternative valid secure designs, state reset/readiness checks and repeated identical-artifact evaluation. Independently audit requirements-to-tests mapping. Freeze the oracle before comparisons. Version defects and rescore all affected preserved artifacts consistently.

**Three tasks remain three tasks.** The proposed 36 runs comprise only three independent task scenarios. Publish the complete task/arm/run matrix descriptively. Run-level binomial intervals or a three-cluster bootstrap do not support population-wide task claims. Later uncertainty methods must respect repository/template/task hierarchy; more repetitions cannot replace task diversity.

**Separate information and representation.** C3–C0 estimates provision of requirements; C4–C3 estimates representation only if independently audited equivalent facts are supplied. Map clauses, assets, assumptions, trust boundaries and attacker capabilities; record lengths and authoring cost. C5 adds discovery/reasoning and is a separate mechanism. One handcrafted threat model cannot establish general threat-modeling efficacy.

**Operationalize budget fairness.** Record allowed and consumed input/output tokens, effort, calls, tools, wall time, review opportunities, retries and costs; leave unavailable internal compute unknown. Security repair requires a nonspecialized-review control. Preserve and score initial and repaired outputs, including regressions. Never feed hidden evaluator findings back into generation.

**Keep LLM review secondary.** Use a fixed reviewer and separate calibration artifacts; blind treatment/writer/outcomes where feasible, noting style/comments can unblind. Review artifacts independently, demand concrete evidence, deduplicate by root cause, classify verified/rejected/unresolved. Precision is measured among adjudicated findings; recall only against a bounded known-defect set. Report adjudicator disagreement and unresolved findings. CWE and severity are not primary numerical outcomes.

**Keep unconditional joint success primary.** Broken/nonstarting applications cannot obtain a standalone security pass; security is unassessable. Security rates conditional on functional success need explicit denominators and may hide functional damage.

**Freeze decisions.** Select one primary contrast, label others exploratory or specify multiplicity handling, separate development/holdout tuning, freeze treatments and failure rules before outcomes, and publish negative/failed runs. Hidden-at-runtime and unseen-in-training are different claims.

## Proposed preregistration record

- Claim, population, estimand, minimum meaningful effect and task selection/families.
- Pinned tasks/model/harness/environment; versioned treatment texts and equivalence audit.
- Primary contrast, exploratory contrasts, randomized/block schedule and repeats.
- Allowed/measured resources; stop/checkpoint and repair rules.
- Oracle qualification, scoring, reviewer calibration/blinding/adjudication.
- Failure/retry/exclusion rules, uncertainty target, multiplicity and stopping policy.
- Version-drift response, publication/holdout/confidentiality policy.

## Proposed failure rules

| Event | Handling to agree before experiments |
| --- | --- |
| Candidate build/start/test failure | Valid development failure; joint score 0; preserve evidence |
| Time/token/turn exhaustion | Budget failure; joint score 0; last eligible checkpoint evaluated only if prespecified |
| Outage/authentication failure before execution | Infrastructure failure; retain original and permit only bounded predefined retries |
| Rate limit/interruption mid-run | Predeclare classification; publish reliability and any rerun; no retry-until-success |
| Evaluator crash independent of candidate | Evaluation error; fix/version/rescore affected artifacts, never security pass |
| Ambiguous LLM finding | Secondary unresolved claim; no silent primary-score revision |
| Test/solution leakage | Contaminated; investigate scope and invalidate affected comparisons |
| Model/harness changes | Pause, version a new block; no silent pooling |

## Smallest next investigation

Review information equivalence and oracle validity on paper during alignment. Then, only with an approved spec, qualify experimental mechanics using a few tasks, one fixed system and C0/C3/C4 if that contrast survives novelty review. Separate prevention-versus-repair into a later study. Owner must select target claim/population, budget, adjudicator, failure rules and meaningful benefit threshold.

This focused critique is not empirical validation or a systematic review. No source establishes reliability of this project's future tests or reviewer.
