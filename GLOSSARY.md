# Principiis Obsta glossary

Principiis Obsta investigates security interventions in AI-assisted software development through controlled experiments.

## Language

**Test environment**:
The research setting in which a coding agent develops an application under a condition and its output is independently evaluated.
_Avoid_: Benchmark, when referring only to the environment rather than a defined collection of tasks and evaluation criteria.

**Security intervention**:
A deliberate change to the agent's development process whose effect on the security and functionality of the generated application is tested.

**Development task**:
A developer work request delivered at one step of an application sequence, with independent functional and security evaluation criteria. The same task is used across compared conditions.

**Application sequence**:
An ordered series of development tasks that builds an application and then evolves it, keeping the evaluated agent's own code. Compared conditions receive the same sequence in independent runs.

**Checkpoint**:
An evaluation point after a development task, assessing current functionality and applicable security properties, including regressions.

**Incremental development**:
The main strategy: the agent receives each step's request only when that step begins, keeps its prior code and never sees later requests.

**Upfront development**:
A comparison strategy in which the agent receives all final requirements in one assignment from a fresh start, with normal planning, tool use and iteration.
_Avoid_: One-shot, when it could be mistaken for a single model response.

**Step session**:
A fresh coding-agent session for one development task. It gets the retained project files (including agent-written notes) and the requests so far, but no earlier conversation or external memory.

**Independent evaluation**:
Assessment of generated artifacts against functional and security criteria whose tests, findings and results stay hidden from the evaluated coding agent.

**Local security review**:
A security intervention that returns review findings to the coding agent to guide later development or repair. It is separate from independent evaluation and cannot access its hidden materials.

**Submission boundary**:
The point at which a development step is ready for a pull request. In the local-review condition, an automatic security review and one bounded repair happen before it.

**Condition**:
A defined development setup applied to an application sequence, such as ordinary development or development with a security intervention.

**Pilot**:
A small baseline-only rehearsal that qualifies the whole path, from task delivery to evaluation and resource accounting, before comparative experiments.
_Avoid_: Hypothesis, test case, when referring to this rehearsal.

**Baseline**:
Ordinary coding-agent development with normal tools and agent-written tests, without researcher-added guidance, skills, review or hooks. Independent evaluation and passive resource measurement still apply.

**Benchmark application**:
A runnable full-stack application that the evaluated agent builds and extends through an application sequence. It is distinct from the test environment that runs and evaluates it.
_Avoid_: Pilot application, mockup, when referring to the software under evaluation.

**Risk opportunity**:
A functionality or interaction where a specified security property must hold. One risk class can have several opportunities, each needing its own evaluation coverage.

**Independent repeat**:
A fresh run of the same application sequence under the same condition and configuration, sharing no artifacts with another run. It measures run-to-run variation.

**Benchmark suite**:
The collection of application sequences and evaluation contracts used to compare conditions.

**Benchmark author**:
The research agent or person who defines scenarios, requests, technology constraints and hidden evaluation contracts. This role may access hidden material; the evaluated coding agent may not.

**Evaluated coding agent**:
The agent whose output is measured under a condition. It receives the released task contract and permitted project context, never hidden evaluator material or author notes.

**Task contract**:
The developer-visible requirements for a development task, including any minimal external interfaces needed for evaluation. Hidden security expectations are defined separately and are not limited to what the request states.

**Security expectation**:
A predefined security property, justified independently of whether the request states it. Its visibility in the request is recorded as stated, implied or absent.

**Evaluator agent**:
An independent agent that investigates additional vulnerabilities with reproducible evidence. Its findings are validated and reported separately from the primary scores, which come from predefined executable checks, and are never returned to the evaluated coding agent.

**Network allowlist**:
The domains the evaluated coding agent's commands may reach through the egress proxy during development. It is built from a logging-only measurement on a disposable fixture, and its digest is part of the runtime version. Its separate **model domains** are reachable only with the model credential.
_Avoid_: Whitelist.

**Model credential**:
A per-attempt token that the egress proxy requires before it forwards to the model domains (the OpenAI/ChatGPT hosts). Only the Codex process gets it; the commands Codex runs get the proxy without it, so they cannot call the model API (and its hosted web search) themselves. It is never logged; only its scheme is part of the runtime version.

**Egress proxy**:
The trusted container that is the development container's only route out of its internal Docker network. It runs in `allowlist` mode for development, or in `log` mode for the measurement. It reaches the internet through its own per-run outside network, never the default bridge.

**Never-allow list**:
The hosts no network allowlist may contain and the egress proxy always refuses in `allowlist` mode: GitHub and services that mirror arbitrary public repositories (`NEVER_ALLOW` in `principiis/egress_proxy.py`).

**Domain fronting**:
Reaching one host through a connection addressed to another, by naming a different server in the TLS SNI or the HTTP `Host` header than in the CONNECT line. The egress proxy refuses an SNI or plain-HTTP `Host` that differs; it cannot see the `Host` inside TLS. A host on a CDN shared with GitHub therefore cannot be tunnelled safely; `network_measurement fronting-check` tests every allowlist host for this before the owner approves it.

**PyPI gateway**:
The read-only Python package index that the egress proxy serves on its own port (`/pypi/simple/`, `/pypi/files/`), so that commands install from PyPI without a tunnel to it. The proxy itself fetches only project index pages from `pypi.org` and package files from `files.pythonhosted.org`, over verified HTTPS with fixed hosts, paths and headers. Those two hosts are **gateway-only**: they share Fastly with `raw.githubusercontent.com`, so no allowlist may list them.

**Model-provider host**:
A host under the registrable domains OpenAI serves Codex, ChatGPT and the API from (`MODEL_PROVIDER` in `principiis/egress_proxy.py`). The egress proxy forwards it only with the model credential, in every mode; no network allowlist may list it in its ordinary domains.

**Network measurement**:
The one logging-only Codex session, on a disposable fixture request, that records which destinations development actually needs. Its egress proxy runs in `log` mode, which still refuses the never-allow list, tunnels to gateway-only hosts, non-public addresses and model-provider hosts without the model credential. Its draft network allowlist is refused until the owner has reviewed it.
_Avoid_: Using a benchmark request for it.

## Example dialogue

Researcher: “Does this security intervention improve the generated application?”
AppSec reviewer: “Compare the same application sequence under each condition and check at every checkpoint whether earlier security properties still hold.”
