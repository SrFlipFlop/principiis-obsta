# Literature and novelty review

Checked 2026-11-14. Consolidated from the independent read-only literature research track. This is a targeted primary-source review, not a systematic review or a novelty guarantee. None of these experiments was independently reproduced. Findings below describe sources; proposed contributions remain hypotheses.

## Verified evidence and overlap

| Source and location | Verified study design | Implication and limitations |
| --- | --- | --- |
| [BaxBench, ICML 2025](https://proceedings.mlr.press/v267/vero25a.html), [v3 §§2–4, Fig. 4/Table 2](https://arxiv.org/html/2502.11844v3) | 392 backend tasks from 28 scenarios × 14 frameworks; executable functionality and exploit evaluation; no, generic and oracle-specific reminders; OpenHands scaffolding analysis | Guidance and oracle requirements already tested. Framework variants are not independent scenarios; account for clustering. |
| [RealSec-bench, ACL Findings 2026, §§4.2–4.3, 5.2–5.3](https://aclanthology.org/2026.findings-acl.1786.pdf) | 105 Java repository-context instances, 19 CWEs, five LLMs; security guidelines and BM25/dense/SAST-dataflow retrieval | Direct context/guidance precedent. CodeQL plus multi-LLM adjudication treats no alert as secure; this cannot detect scanner false negatives and differs from behavioral oracles. |
| [DualGauge, EMNLP Findings 2026, §§4–5, §8, App. E](https://aclanthology.org/2026.findings-emnlp.1335.pdf) | 307 specification-only tasks, ten main models, three languages and three coding-agent systems; execution plus model judgments; reported evaluator F1 0.895 against human labels | Joint evaluation is established; evaluator accuracy varies across weaknesses. Prefer qualified PDF conclusions over landing-page summaries. |
| [SusVibes v4, §§3–5, Table 5, App. C](https://arxiv.org/html/2512.03262v4) | 186 real-repository feature tasks, twelve agent/model configurations; generic guidance, self-selected risks and oracle hints | Direct overlap with C1/C2/C3/C5-like conditions. Security gains can accompany functionality loss; SecPass is already joint success. |
| [Agent Security League, Methodology/metric footnotes](https://www.endorlabs.com/research/ai-code-security-benchmark) | Commercial SusVibes-derived comparison of agent-plus-model systems, with sanitization/cheating detection; methodology names 200 tasks | Version differs from current 186-task SusVibes. Percentages are not directly comparable without exact fork/task/evaluator alignment. Commercial claims are not independent replication. |

## Additional intervention work

- [Applying Security by Design at the Point of Execution, Farinha, October 2026 preprint](https://arxiv.org/html/2610.10659v1), §§2–5, 7–9: selected requirements delivered through MCP; evaluates 59 DualGauge tasks and 28 BaxBench scenarios. The prespecified joint secure-and-functional outcome did not improve significantly. Single generations, post-hoc analyses and author ownership of the system limit conclusions. Direct overlap with curated requirements/adaptive context. Absence of significance does not establish absence of an effect.
- [Bruni et al., FORGE 2025](https://arxiv.org/html/2502.06039v1), §§III–V, VII: prompting and iterative critique/repair on three GPT models with static scanners and repeated sampling. Functionality is measured on separate HumanEval tasks, so scanner improvements do not demonstrate joint gains on the security tasks.
- [Rethinking the Evaluation of Secure Code Generation, ICSE 2026](https://tao.aisec.world/assets/pdf/ICSE26.pdf), §§3–4, Tables 4–6: reexamines SVEN, SafeCoder, CodeGuard+ and PromSec using same-program functional/security evaluation, multiple analyzers and model-assisted inspection. Detector disagreement and functional regressions undermine simple security claims. Constraints and scanner-driven prompt refinement have precedent.
- [SecureVibe, September 2026 preprint](https://arxiv.org/html/2609.38606v1), §§3–4, Tables 1–2, App. E: trains security planning/coding/testing with Qwen 3.5 35B and mini-swe-agent; repeated trials and transfer to BaxBench/SusVibes. Reported eight-B200 training setup reinforces deferring training.
- [TRACER: Securing Agent-Generated Code with Its Own Development History, October 2026 preprint](https://arxiv.org/html/2610.34098v1), §§IV–V, Table II, §IX: 3,096 repair runs using history/rationale versus snapshot/SAST review, two investigator models and task-cluster bootstrap. Admission requires prior functionality; these are conditional repair outcomes, not whole-benchmark generation rates.
- [SecPI, April 2026 preprint](https://arxiv.org/abs/2604.03587): abstract verified only; structured security-reasoning distillation and reported joint gains. Full methods/statistical review outstanding.
- [GoodVibe, February 2026 preprint](https://arxiv.org/html/2602.10778v1), abstract/§§3–5: neuron-selective fine-tuning. Relevant to deferred specialized models, not evidence for our proposed inference-time workflow.

## Critical assessment — inference

Broad claims that security guidance, planning, selected context or repair are new are untenable. Joint functional/security scoring is a methodological requirement, not novelty. A candidate contribution is C3 versus C4 with audited identical security facts and controlled preparation/generation opportunity. Another is prevention versus security repair versus generic extra review with declared budgets and initial/final snapshots. Neither candidate's priority is established by this search.

A transparent replication investigating requirements/functionality conflicts may be useful even without a new method. A negative result can be valuable if oracle contracts and analysis are frozen first.

## Next investigation and unresolved evidence

Audit Farinha, BaxBench prompting, SusVibes §5 and CodeGuard+ in detail before choosing a claim. Check whether threat-model headings introduce trust-boundary facts or implementation hints. Full matrices, statistical procedures and contamination measures were not exhaustively extracted for every work; missing fields must remain unknown. Separate source versions and peer-reviewed results from preprints/commercial pages. Owner must choose causal intervention study versus new benchmark, intended task population, requirements provenance and acceptance of a null result.
