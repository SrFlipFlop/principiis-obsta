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

## Example dialogue

Researcher: “Does this security intervention improve the generated application?”
AppSec reviewer: “Compare the same application sequence under each condition and check at every checkpoint whether earlier security properties still hold.”
