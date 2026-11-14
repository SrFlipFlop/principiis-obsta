# Literature and tools to verify and build upon

**Status:** starting map refreshed by four independent research tracks on 2026-11-14. See [verified literature report](research/01_LITERATURE_NOVELTY.md), [reuse report](research/02_BENCHMARK_REUSE.md) and [synthesis](research/05_SYNTHESIS.md). This remains a targeted review, not a systematic review or novelty guarantee.

## Primary scientific benchmarks

1. **BaxBench — Vero et al., ICML 2025**. 392 backend application-generation tasks from 28 scenarios × 14 frameworks; functional and security evaluation with executable tests/exploits. https://proceedings.mlr.press/v267/vero25a.html ; https://baxbench.com/ . **Question:** can some task/evaluator infrastructure be reused, rather than inventing it?
2. **RealSec-bench — Wang et al., Findings of ACL 2026**. 105 real-repository Java instances spanning 19 CWEs. Reports that generic security instructions may hurt compilation/functionality without consistently improving security, and RAG mainly helps functionality. https://aclanthology.org/2026.findings-acl.1786/ ; https://github.com/DeepSoftwareAnalytics/Realsec-code-Bench . **Question:** how to isolate contextual security guidance versus downstream review?
3. **DualGauge — Patir et al., Findings of EMNLP 2026**. Joint security/functional benchmark of 307 specification-only tasks in the later publication; early arXiv v1 describes 154. Evaluation includes model judgments, not just deterministic tests. https://aclanthology.org/2026.findings-emnlp.1335/ ; https://github.com/SRestLabUB/DualGauge . **Question:** can its evaluation design inform independent security checks?
4. **SusVibes — LeiLiLab, ICML 2026**. Security implications of agent-generated code in realistic feature-development tasks; current v4/v1.0 has 186 tasks; earlier v0.0 had 200. Includes generic, self-selected and oracle security prompting, not only model comparisons. https://github.com/LeiLiLab/susvibes . **Question:** validate findings in existing repositories and guard against fix leakage.
5. **Agent Security League — Endor Labs**. Public comparisons of agent/model system configurations with functional and security correctness metrics. https://www.endorlabs.com/research/ai-code-security-benchmark . **Question:** explicitly separate agent+model leaderboard comparison from interventions on a fixed agent.

## Existing interventions and engineering projects

6. **Anthropic Claude Code security-guidance plugin**. Hooks and security guidance, potentially a comparison arm, not a new technique to rebuild. https://github.com/anthropics/claude-plugins-official/tree/main/plugins/security-guidance . Current source includes edit warnings and asynchronous model review; pin reviewer/model/configuration and record whether review actually ran. See the harness report for documentation inconsistencies.
7. **Trail of Bits skills**. Security research/audit workflow skills, reference for structured, on-demand security context. https://github.com/trailofbits/skills .
8. **Google Elephant & Goldfish Model (EGM)**. Design drafting and fresh-context review workflow. https://github.com/google/elephant-goldfish-model . Useful methodology/integration inspiration; not itself evidence that a threat model prevents vulnerabilities in generated code.
9. **OWASP ASVS**. Source of measurable AppSec acceptance criteria, not a monolithic prompt to paste into model context. https://asvs.owasp.org/ .
10. **Matt Pocock's engineering skills**. Human/agent alignment, glossary/ADRs, spec → tickets → implementation/review. This governs *how to develop this research project*; it is not evidence supporting a benchmark intervention. https://github.com/mattpocock/skills .
11. **Codex subagents documentation**. Project-scoped `.codex/agents/*.toml` and explicit delegation. https://learn.chatgpt.com/docs/agent-configuration/subagents .

## Novelty test for literature subagent

For each paper/project, answer with source locations: (a) task/unit, (b) agent/model matrix, (c) interventions tested, (d) evaluator and ground truth, (e) sample size and statistics, (f) contamination mitigation, (g) what **our** proposed study would add, if anything. Include limitations and avoid claiming novel results just because terminology differs.

## Corrections and direct intervention precedents

The initial map understated prior intervention comparisons. BaxBench tests generic/oracle reminders; SusVibes tests risk selection/oracle hints; RealSec-bench tests retrieval/guidelines. See the [literature evidence table](research/01_LITERATURE_NOVELTY.md) for primary-source locations. Additional close work includes governed security requirements at generation time, secure-code evaluation reanalysis, prompt/repair studies, SecureVibe and history-assisted TRACER repair. The report distinguishes peer-reviewed work, preprints and abstract-only leads. Broad prevention or joint-scoring novelty is unsupported.

Reuse licenses: BaxBench and SusVibes repository software is MIT, with per-task/data/image provenance still requiring audit. DualGauge permission remains unverified. SusVibes aggregate `sec_pass` already includes functionality. Do not compare metrics across versions without fixing task sets and evaluators.

## Iterative-development precedent raised during alignment

Checked 2026-11-14: [SlopCodeBench paper v1, §§2.1–2.3](https://arxiv.org/html/2603.24755v1) carries generated workspaces across evolving requirements and evaluates intermediate checkpoints. Its erosion/verbosity metrics concern maintainability, not validated security properties. The [current runner README](https://github.com/SprocketLab/slop-code-bench) describes an evolving evaluation primitive. Counts differ across versions; do not combine releases. Reuse licensing, security applicability and oracle quality have not been audited.

Proposal: an initial application followed by feature changes could connect both desired task types. A matched fresh-build control with the same final requirements would help distinguish accumulated-history effects from increased task difficulty. This is a design option, not an approved protocol or demonstrated novelty.

### Checkpoint sizing comparison

Checked 2026-11-14: [SlopCodeBench v1, §2.2 / Progress phases](https://arxiv.org/html/2603.24755v1) uses 3–8 checkpoints per problem, carrying generated workspaces forward without prior conversational context. Our owner-selected target is ten steps per application. This is a sizing choice, not evidence of greater realism or benchmark quality; exact requirements and evaluator validity remain decisive. Later releases may differ from v1.
