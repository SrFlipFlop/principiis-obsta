# Evaluator material is published; the evaluated coding agent is network-limited

Accepted by the owner on 2026-11-27, after the #72 investigation ([issue #73](https://github.com/SrFlipFlop/principiis-obsta/issues/73)). Evidence and alternatives are in [research note 08](../research/08_PRIVATE_MATERIAL_STORAGE.md).

## Context

Hidden checks, control results and the Codex login all sit in one operator's git-ignored `private/` folder. Other machines and sessions can't use them, which is the problem #9 ran into. Bound runs store the evaluator's absolute path, so moving the folder breaks them.

Keeping the tests secret doesn't buy much:

- every request of every benchmark is already public in this repo;
- the evaluated coding agent has full network access, so it can reach them anyway;
- most coding benchmarks publish their tests, because readers need every detail to check and rerun an experiment.

The secrecy that matters is from the evaluated coding agent while it develops, not from readers.

## Decision

- **Tests and controls are public in this repo.** Each evaluator version, its declaration, check definitions, seccomp profile and image recipes live under `benchmarks/<app>/evaluator/<version>/`. Its control implementations and results live under `benchmarks/<app>/controls/<version>/`. Published test files carry a canary string.
- **Docker images are published after the paper.** The exact evaluator and runtime images, which runs pin by ID, are published once the experiment is done and the paper is out. Until then, they are shared privately when needed.
- **Only credentials and personal details stay private.** The Codex login and `runtime.json` live in the operator's home folder, outside every repository. Host paths and usernames in run records are removed before run records are shared.
- **The evaluated coding agent is protected by network limits, not by hidden files.**
  - Web search is disabled.
  - Command network access is limited to an allowlist (the model API, package registries and any documentation actually needed).
  - The allowlist is built from a logging-only measurement on a disposable fixture.
  - Workspaces start without research-side Git history.
- **Runs find evaluator files by content hash, not absolute path.** New runs also copy the evaluator files they bind. Existing runs stay unchanged and resolve through a hash lookup.
- **Tests stay out of public Git until the network limits are in place.** Until then, an agent could still find them on GitHub.

## Consequences

- AGENTS.md hard rule 1 forbids hidden checks and evaluator material in public Git. It must be changed by the owner before tests move. Future requests are also already in public Git, which the rule's current wording doesn't reflect. The new wording should keep the core of the rule: nothing hidden or future may reach the evaluated coding agent's context.
- Collaborators get everything except images and credentials by cloning this repo. A rebuild from the recipe usually gives a different image ID, so evaluating existing runs on another machine needs a private copy of the image until publication.
- Runs made before the network limits had full network access and live web search. Their results must say so.
- Once tests are public, future models may train on them. Canaries help only with cooperative trainers. Comparisons that use models trained after publication may need new or rotated steps.
- A private sibling repository, encrypted files in this repository (git-crypt, SOPS/age, git-secret) and embargoed archives were considered and not chosen. Each kept the tests hidden, which neither protects the evaluated coding agent while requests are public nor helps readers.
- **Open:** whether run results (logs, scores) are public during the experiment or only after the paper.
- Implementation is tracked in #75; the decisions-log entries are tracked in #74.
