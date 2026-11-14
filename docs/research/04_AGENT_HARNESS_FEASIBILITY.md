# Agent harness and local-model feasibility

Checked 2026-11-14. Independent read-only harness research track. Official documentation/local help only; no installation, authentication inspection, model calls or execution experiments. Capabilities are not measured efficacy.

## Compatibility matrix

| System/source location | Verified support | Limits/consequences |
| --- | --- | --- |
| Codex CLI 0.169.0 local help; [noninteractive mode, machine-readable output/authentication](https://learn.chatgpt.com/docs/non-interactive-mode) | `exec`, JSONL events, output schema/final-message output, explicit model, sandbox and local provider selection | Save events/stderr/exit status/patches, not only final prose. Saved auth reuse and account-automation restrictions need review before running. |
| [Codex authentication, API keys](https://learn.chatgpt.com/docs/auth?surface=cli) | ChatGPT-managed access differs from separately billed API access | Subscription does not imply unlimited experiment capacity or API credit. No paid mode approved. |
| [Codex hooks, lifecycle/trust](https://learn.chatgpt.com/docs/hooks) | PreToolUse/PostToolUse/Stop/model-request and other events; project/user/plugin discovery; hash-based trust | Notification-only assumption is stale. Validate exact installed behavior later; matching hooks may run concurrently. |
| [Claude programmatic execution](https://code.claude.com/docs/en/headless), [CLI flags](https://code.claude.com/docs/en/cli-reference) | `claude -p`, JSON/stream JSON, tools/model/effort controls, max turns and estimated max-budget-usd | Dollar cap is estimated and may be exceeded; turn caps are not equal-compute guarantees. |
| [Claude authentication precedence](https://code.claude.com/docs/en/authentication); [bare mode](https://code.claude.com/docs/en/headless) | ANTHROPIC_API_KEY takes precedence in noninteractive mode; ordinary print mode discovers instructions/hooks/skills/plugins/MCP; bare mode changes discovery and authentication | Record credential mode, never secrets. Bare mode may remove the intended treatment and alter subscription availability. |
| [LM Studio OpenAI endpoints](https://lmstudio.ai/docs/developer/openai-compat), [Codex integration](https://lmstudio.ai/docs/integrations/codex), [Claude integration](https://lmstudio.ai/docs/integrations/claude-code) | Responses endpoint and Anthropic-compatible Messages integration; Codex guidance recommends over roughly 25k context | Protocol compatibility does not establish tool-use reliability or local hardware adequacy. |
| [Ollama Codex setup](https://docs.ollama.com/integrations/codex), [OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility) | codex --oss; recommends at least 64k context; partial OpenAI compatibility | Pin model/hash/quantization/context/backend. Cloud models/search exist; Ollama does not automatically imply offline execution. |
| [Docker resource constraints, introduction/Memory/CPU](https://docs.docker.com/engine/containers/resource_constraints/) | Containers have no resource limits by default; explicit limits supported | Set/verify limits and network/mount/privilege restrictions. No task-specific overhead estimate yet. |

Local inspection found Docker at `/snap/bin/docker`; `claude`, `ollama` and `lms` were absent from this shell's PATH. This does not establish absence of Windows installations or external services. Docker daemon access/functionality was not tested.

## Existing security-guidance intervention

The [official manifest](https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/plugins/security-guidance/hooks/hooks.json) and [hook implementation](https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/plugins/security-guidance/hooks/security_reminder_hook.py), module description/configuration, describe edit-pattern warnings, session preparation and asynchronous diff-based model review on stop/Git actions. Review availability depends on credentials. Introductory text mentions Haiku while configuration prose names newest Opus: pin a commit and inspect executable selection logic, explicitly choose reviewer and verify each review occurred. Do not infer effective model from prose. No intervention efficacy follows from its existence; asynchronous behavior complicates snapshots/budget accounting.

## Recommendations — not architecture decisions

1. Start with one pinned agent/model/configuration. Codex-versus-Claude is an agent-system comparison.
2. A common CLI is insufficient for a pure model claim unless prompts, tools, permissions, context/compaction, reasoning and stops are controlled. Backend templates and tool protocols may still confound.
3. For a later repair experiment, explicit generation → snapshot → review → bounded repair may be easier to measure than native asynchronous hooks.
4. Keep inference credentials in a controller outside untrusted application/evaluator containers. Separate controller network needs from application restrictions.
5. Account for selection, discovery, review, repair, retries and subagents. Actual API bills, API-equivalent estimates and subscription marginal charges are different quantities.
6. Fresh sessions/configuration per trial; isolate memory, user instructions, plugins, MCP and content-bearing caches. Resume only within prespecified stages.
7. Record CLI/backend/model identifiers, local hashes/quantization/context, effort/decoding, treatment hashes, image digests and integrations. Prevent automatic updates during a frozen study.

## Feasibility and open questions

Existing CLIs appear sufficient for a small study; no general adapter framework is justified yet. Hardware, account limits, stable model access, tool-call reliability and evaluator resource needs remain unknown. There is no defensible dollar/throughput/memory forecast without an approved dry run.

After alignment, an approved non-paid harmless-fixture check could establish logs, configuration isolation, stopping, resource limits and artifact capture. Local-model work should follow only if necessary for the selected scientific claim. Owner must choose fixed system, credential mode, hardware/storage budget, native hooks versus explicit review, resource cap, retry policy and drift controls.

## Process-observation clarification during alignment

Verified 2026-11-14: [Codex noninteractive docs, Make output machine-readable](https://learn.chatgpt.com/docs/non-interactive-mode) list reasoning items alongside messages, commands, changes and tool calls in JSONL events. Local `codex exec --help` confirms `--json`; no model run was performed to establish actual content/completeness. [OpenAI reasoning guide, Reasoning summaries / Preserve reasoning across calls](https://developers.openai.com/api/docs/guides/reasoning) distinguishes exposed summaries from unexposed raw reasoning. API summary support does not guarantee identical CLI availability.

Proposal: analyze observable security-related actions, code evolution, checks and exposed summaries as exploratory process evidence. A security claim in a summary is not proof of a control, and no mention does not prove lack of awareness. Asking for extra explanations can itself change the treatment; prefer passive collection initially. Mechanism attribution requires controlled comparisons, not just narrative interpretation.

## Hook-to-reviewer clarification

Checked 2026-11-14: [official hooks reference, handler notes / Stop / PostModelRequest](https://learn.chatgpt.com/docs/hooks) supports command/MCP handlers; native `agent`/`prompt` handlers are parsed but skipped. Stop feedback can continue the writer. Per-request usage can be null. Proposal: a command handler could invoke a separate noninteractive reviewer and pass findings back; invocation, recursion prevention and usage completeness need post-alignment validation on CLI 0.169.0. No hook or reviewer was executed.
