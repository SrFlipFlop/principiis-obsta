# Planned development-workflow skill condition

**Status:** owner-selected research direction from the 2026-11-20 discussion; proposed intervention design for [issue #52](https://github.com/SrFlipFlop/principiis-obsta/issues/52). It does not change the baseline in [PROJECT.md](../PROJECT.md); interventions are out of scope right now. The [source survey](research/07_DEVELOPMENT_SKILLS.md) records candidate skills, pinned upstream revisions, licenses, compatibility questions and uncertainty.

## Question and hypothesis

Does an explicit, reusable **plan–implement–verify** workflow change the proportion of development-task checkpoints that pass required functionality **and** applicable security properties, compared with ordinary Codex development on the same application sequences? The directional hypothesis is that the workflow improves this joint outcome, especially on large initial builds and multi-part changes; it may instead have no effect or harm completion by adding overhead. This is a hypothesis, not a finding. It gives no security-specific advice.

The treatment is the **whole custom workflow**, including its invocation instruction. A difference cannot identify the effect of planning, small units, diagnosis or verification individually. A later study could isolate them if the bundle-level contrast warrants it.

## Skill behavior to draft and version

Create one small custom skill inspired by Poteto's `principle-sequence-verifiable-units` and `principle-prove-it-works`, and the relevant parts of Pocock's `codebase-design` and `diagnosing-bugs`. Write original, concise instructions; inspect and attribute upstream source at the pinned revisions in the [survey](research/07_DEVELOPMENT_SKILLS.md) and preserve license notices if text is copied. The skill should instruct the agent to:

1. **Read the current request and available project context.** Use only requirements revealed so far. For an existing application, identify the affected public behavior and nearby modules. For a bug report, try to reproduce the reported symptom with visible evidence before choosing a fix; record when reproduction is impossible.
2. **Make a proportionate plan.** Turn a multi-part objective into a short ordered list of user-observable work units. Give each unit a completion check that can be run with the agent's ordinary tools. A genuinely small request may be one unit. Do not ask a human to approve a test seam, create GitHub issues, spawn additional agents, or require commits between units.
3. **Implement and check one unit at a time.** Use an appropriate visible test, build, browser/API check or other reproducible observation. If a check fails, diagnose it before proceeding. Never treat an agent-written test as the hidden independent oracle.
4. **Check the integrated result.** Recheck the current request and relevant prior behavior through available public interfaces. Report what ran, failed, or could not be checked. Do not claim a security or functional guarantee from an incomplete check.

The exact `SKILL.md`, trigger text, optional references and any condition launcher are **not yet frozen artifacts**. Keep the skill free of benchmark-specific solutions, hidden properties, future requests and security prescriptions. This first condition does not include upstream `grill`, `to-spec`, `to-issues`, `implement`, mandatory TDD, automatic review/repair or threat-model specifications; those would add interactions, issue-tracker access or other mechanisms.

## When and how it is applied

The same base developer request bytes and cumulative prior requirements go to both conditions. On **each** fresh development step session, after the current request is available, the treatment agent is explicitly directed by a separate, versioned condition instruction to use the custom skill on that request. The instruction is part of the treatment, stored and hashed separately from the benchmark request. The baseline receives neither the instruction nor the skill. Mere installation would test discovery and voluntary use, which is a different question; it is not the first planned contrast.

Stage the pinned skill in a disposable session environment for every step and explicit retry, outside retained application snapshots. Keep condition files and launcher artifacts out of the baseline, and do not copy the research account's skills or instructions. Preserve agent-authored project notes normally within each independent condition run; no notes or code cross from one condition to another. The exact discovery path and explicit invocation mechanism must be qualified against the pinned Codex CLI. The current [container development adapter](../principiis/development_runtime.py) launches a clean, ephemeral Codex session and has no demonstrated skill-treatment path; this document does not claim it already works.

The agent may make its plan in its normal visible work output or project notes, depending on what the pinned harness exposes. Do not add a special planning API or force explanations that ordinary agents would not provide beyond the treatment's short plan. Observe available metadata, file reads and actions separately: a staged skill, a loaded skill and a followed workflow are different observations.

## Comparison and qualification

Keep task source, model and reasoning settings when exposed, Codex version and harness, ordinary tools, permissions, runtime image, network setup, retry policy, feedback boundary and hidden evaluator fixed across conditions. Freeze task, condition and evaluator versions before comparison. The primary checkpoint score is the predefined executable **functional AND security-property pass**. Report failures and unassessable outcomes. Secondary evidence includes regressions, visible check completion, plan/unit counts, elapsed time, reported tokens, tool use, local memory with measurement scope, and independently assessed maintainability if a rubric is specified in advance. Count incomplete attempts and separate development from evaluation cost. A single run per application and dependent checkpoints support descriptive comparison only, not stochastic efficacy claims.

Before proposing a comparative run, use a disposable **non-benchmark** fixture with a large request, a small request, a change to existing code and a bug report. Verify unchanged base request bytes; isolated delivery and removal of treatment files; explicit skill activation at each fresh session and retry; proportionate planning; no unrequested human/issue-tracker gate; no future or hidden materials in context; and complete artifact/cost capture. Record missed or unintended activation. If the exact skill cannot be invoked in the normal Codex harness, revise and requalify the treatment artifact rather than assume the workflow happened.

## Remaining decisions

- Draft and review the exact custom skill and separate invocation text, with hashes and source attribution.
- Confirm a supported delivery path and audit events in the pinned runtime; implement only after the baseline path and oracles qualify.
- Decide the comparison's task sample, repeat count, analysis and meaningful effect threshold before execution. A broader efficacy claim needs independent repeats and uncertainty analysis.
- Agree the comparative run's timing with the owner; live runs follow the hard rules in [AGENTS.md](../AGENTS.md).
