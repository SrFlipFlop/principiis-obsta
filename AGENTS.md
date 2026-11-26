# Principiis Obsta

Principiis Obsta tests interventions that aim to make coding agents write more secure code. A coding agent builds benchmark applications step by step under an experiment condition, and hidden functional and security checks score each step.

Read [`PROJECT.md`](PROJECT.md) before working.

## Hard rules

1. Hidden checks, evaluator material (`private/`) and future requests must never reach the evaluated coding agent's context, public Git, issues or PRs.
2. No paid API runs.
3. No live Codex subscription runs without asking the owner.
4. Don't push or publish (PRs, issues, comments, releases) unless the owner asked for it in the session.

## Engineering preferences

- Work in small vertical slices.
- Write tests first.
- Run the suite (`python3 -m unittest discover -s tests -q`) and report the results, including failures and skips.

## Agent skills

- Issue tracker: GitHub Issues in `SrFlipFlop/principiis-obsta`; see `docs/agents/issue-tracker.md`.
- Triage labels: the five standard triage roles; see `docs/agents/triage-labels.md`.
- Domain docs: `GLOSSARY.md` and `docs/adr/`; see `docs/agents/domain.md`.
