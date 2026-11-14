# Benchmark reuse and oracle feasibility

Checked 2026-11-14. Independent read-only benchmark track, consolidated by parent. No benchmark artifacts, solutions, exploit code, images or dependencies imported. Reuse feasibility is documentary, not execution-validated.

## Verified evidence

| Source and exact location | Findings | Consequences |
| --- | --- | --- |
| [BaxBench site, task/testing descriptions](https://baxbench.com/); [README, release/Usage](https://github.com/logic-star-ai/baxbench/blob/main/README.md) | 28 scenarios × 14 frameworks = 392 tasks; OpenAPI/text specs; functional and black/white-box security checks. v1.0.0 README supports scenario/framework filters, separate generation/testing and external code import; Python 3.12, Docker, Pipenv | Existing evaluator may be reused without its generator. Application generation differs from repository modification. No runtime feasibility measured. |
| [BaxBench LICENSE](https://github.com/logic-star-ai/baxbench/blob/main/LICENSE) | MIT software license | Retain notices and separately audit data/dependency provenance. |
| [SusVibes README, Dataset/Evaluation](https://github.com/LeiLiLab/susvibes) | Current version: 186 repository-feature tasks, patch submissions and prebuilt images. Full evaluation recommends 300 GB free storage; 4 GB RAM/4 CPU per worker | Closest task-unit match, but full evaluation is heavier than a small subset. These are upstream recommendations, not measured local overhead. |
| [SusVibes evaluator, result/aggregate sections](https://github.com/LeiLiLab/susvibes/blob/main/susvibes/eval/README.md) | Removes test/binary patch edits; compares functional tests to golden-reference failures; adds security test patch. `sec_pass` means functional AND security pass, denominator all candidates; infrastructure indeterminacy separate | Audit baseline comparison and ensure new-feature functionality is tested, not merely old regressions. |
| [SusVibes strategies, Available Strategies](https://github.com/LeiLiLab/susvibes/blob/main/susvibes/eval/strategies/README.md) | Generic/self-selection/oracle/sec-test documented; feedback-driven marked Coming soon despite top-level naming. sec-test reveals evaluation tests | Test visibility is privileged information, not a hidden-evaluation treatment. Presence in CLI/README is not proof of implementation. |
| [SusVibes LICENSE](https://github.com/LeiLiLab/susvibes/blob/main/LICENSE), [CHANGELOG v1.0](https://github.com/LeiLiLab/susvibes/blob/main/CHANGELOG.md) | MIT repository; 200-task v0.0 changed to 186-task v1.0; discusses false failures from fix-derived tests and reward-hacking repairs | Audit incorporated repositories/images individually. Pin revisions; don't pool old/new results. |
| [DualGauge README](https://github.com/SRestLabUB/DualGauge), [PIPELINE §§1, 4.3–4.7, 5](https://github.com/SRestLabUB/DualGauge/blob/main/PIPELINE.md) | 307 spec-only tasks; tests.json, agentic instrumentation/execution and model verdicts. Documents API-key injection into execution containers | Different task unit and partly model-based oracle. Do not adopt secret injection into untrusted code containers. |

DualGauge [arXiv v1 §§III/V](https://arxiv.org/html/2511.20709v1) describes 154 tasks; current README and later publication describe 307. Keep versions distinct. No reusable DualGauge code/data license was verified: no root LICENSE in inspected listing and direct fetch failed. Public access does not establish permission.

BaxBench [paper v3 §2.1/Limitations](https://arxiv.org/html/2502.11844v3) describes human-reviewed controls and refined tests, while acknowledging incomplete tests and future contamination. Withholding golden solutions alone cannot establish freedom from training overlap.

## Options — proposals

| Option | Benefit | Cost/limitation |
| --- | --- | --- |
| BaxBench subset | Existing executable backend evaluator and prior prompting comparison | Changes study unit; strong novelty overlap |
| SusVibes subset | Realistic repository modifications | Images, historic-fix leakage, licensing and oracle overspecification |
| Three custom tasks | Tight control over treatment semantics | Entire oracle-validation burden; little generalization |
| Hybrid | External comparability plus fresh checks | More curation, heterogeneous units; stratify rather than merge headline scores |

Recommendation: after alignment, inspect metadata-only shortlists from BaxBench and SusVibes and choose one task unit. Do not build a universal adapter first. C0/C3/C4 on one fixed system is a plausible engineering pilot; no arm choice is approved.

## Proposed qualification and leakage checks

1. Pin commits, dependency versions and image digests; audit selected artifact licenses.
2. Allowlist generator-visible files. Exclude researcher notes, task metadata/CWE labels, security tests, reference patches, Git history and remote access.
3. Inspect image contents; a clean working tree does not remove hidden historical/evaluator material.
4. Validate secure, property-violating and reject-everything controls, including multiple acceptable secure designs. Repeat evaluator-only runs for flakiness.
5. Confirm functional tests actually require the new feature.
6. Preserve initial/final hashes; prevent test/evaluator mutation; define infrastructure retries before runs.
7. Tune only on development tasks; freeze held-out tasks before comparing arms. Disclose public exposure and uncertain pretraining overlap.

## Open questions

Choose task unit, reuse/custom strategy, acceptable contamination risk, independent oracle auditor, storage/hardware budget, and minimum task diversity. Task curation and oracle validity are more uncertain than runner architecture.
