# Principiis Obsta research context

Principiis Obsta investigates security interventions in AI-assisted software development through controlled experiments.

## Language

**Test environment**:
The research setting in which a coding agent develops a security-sensitive application under an experimental condition and its output is independently evaluated. The environment supports investigation of multiple hypotheses.
_Avoid_: Benchmark, when referring only to the environment rather than a defined collection of tasks and evaluation criteria.

**Security intervention**:
A deliberate change to the agent's development process whose effect on generated application security and functionality is investigated experimentally.

**Development task**:
A developer work request delivered at one step of an application sequence, with independent functional and security evaluation criteria. The same task is used across the intervention conditions being compared.

**Application sequence**:
An ordered series of development tasks that begins with an application and evolves it through feature changes, preserving the evaluated agent's own code. Compared intervention conditions receive the same sequence in independent runs.

**Checkpoint**:
An evaluation point after a development task in an application sequence, assessing current functionality and applicable security properties, including regressions.

**Incremental development**:
The main experimental strategy, in which the agent receives each application-sequence step only when that step begins, retaining its prior code without advance access to later requests.

**Upfront development**:
A comparison strategy in which the agent receives all final requirements in one assignment from a fresh starting state, with normal planning, tool use, testing and revision.
_Avoid_: One-shot, when it could be mistaken for a single model response.

**Step session**:
A fresh coding-agent session for one development task in an application sequence. It receives retained project files, including agent-authored notes, and requirements revealed so far, without prior conversation history or external session memory.

**Independent evaluation**:
Assessment of generated artifacts against functional and security criteria whose tests, findings and results remain hidden from the evaluated coding agent.

**Local security review**:
A security intervention that returns review findings to the coding agent to guide subsequent development or repair. It is separate from independent evaluation and cannot access its hidden materials.

**Submission boundary**:
The point at which a development step is considered ready for a pull request. In the local-review condition, an automatic security review and bounded repair opportunity occur before submission.

**Condition**:
A defined development setup applied to an application sequence, such as ordinary development or development with a security intervention.

**Pilot**:
A small baseline-only rehearsal that qualifies the complete path from task delivery through agent execution, artifact retention, independent evaluation and resource accounting before comparative experiments.
_Avoid_: Hypothesis, test case, when referring to this rehearsal.

**Baseline**:
Ordinary coding-agent development with normal tools and agent-authored tests, without researcher-added guidance, skills, review or behavioral hooks. Independent evaluation and passive resource monitoring still apply.

**Benchmark application**:
A runnable full-stack application, including frontend and backend, that the evaluated agent builds and extends through an application sequence. It is distinct from the test environment that executes and evaluates development runs.
_Avoid_: Pilot application, mockup, when referring to the software under evaluation.

**Risk opportunity**:
A functionality or interaction where a specified security property must hold. The same risk class can have multiple opportunities within and across benchmark applications, each requiring its own evaluation coverage.

**Independent repeat**:
A fresh run of the same application sequence under the same condition and configuration, beginning from the same starting state without inheriting another run's artifacts. It measures run-to-run variation separately from differences between applications.

**Benchmark suite**:
The collection of benchmark application sequences and their evaluation contracts used to compare development conditions. Each application provides multiple development tasks and risk opportunities.

**Benchmark author**:
The research agent or person defining application scenarios, development requests, technology constraints and independent evaluation contracts. This role is separate from the evaluated coding agent and may access hidden evaluation materials.

**Evaluated coding agent**:
The agent whose development output is measured under a condition. It receives the released task contract and permitted project context, without hidden evaluator materials or benchmark-author notes.

**Task contract**:
The observable requirements for a development task, including the minimal external API routes, request/response formats and behavior needed for evaluation. It leaves internal architecture and frontend design open within the application's selected technology constraints.

**Evaluator agent**:
An independent agent that runs hidden functional/security checks and investigates additional vulnerabilities using reproducible evidence. Primary scores come from predefined executable checks, while agent-discovered findings are separately validated and reported; neither is returned to the evaluated coding agent.

## Example dialogue

Researcher: “Does this security intervention improve the generated application?”
AppSec reviewer: “Compare the same application sequence under each condition and check at every checkpoint whether earlier security properties still hold.”
