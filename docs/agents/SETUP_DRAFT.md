> Historical applied setup from 2026-11-14. Current instructions are [domain documentation](domain.md) and the [development workflow](workflow.md); the snippets below preserve the former `CONTEXT.md` convention.

# Matt Pocock repository setup — applied draft

The owner selected GitHub Issues, standard triage names and a single context on 2026-11-14. The displayed draft was applied after the owner invoked `/setup-matt-pocock-skills` to complete setup. It does not create GitHub resources or approve implementation.

## AGENTS.md addition

```markdown
## Agent skills

### Issue tracker

GitHub Issues in `SrFlipFlop/principiis-obsta`; see `docs/agents/issue-tracker.md`.

### Triage labels

Use the five standard triage roles; see `docs/agents/triage-labels.md`.

### Domain docs

Single context: `CONTEXT.md` and `docs/adr/`, created lazily during alignment; see `docs/agents/domain.md`.
```

## docs/agents/issue-tracker.md

Issues and PRDs live in GitHub Issues for `SrFlipFlop/principiis-obsta`. Use `gh` from this checkout. Read tickets with `gh issue view <number> --comments`; list with `gh issue list`. When an explicitly invoked workflow requests publication, create the requested issue. For multiline bodies write a temporary UTF-8 file and pass `--body-file`; preserve exact text. Do not create issues or modify remote resources during research setup. Keep hidden evaluator material and confidential data out of tickets.

## docs/agents/triage-labels.md

| Role | GitHub label |
| --- | --- |
| Needs evaluation | `needs-triage` |
| Waiting on reporter | `needs-info` |
| Ready for autonomous implementation | `ready-for-agent` |
| Requires human work | `ready-for-human` |
| Will not be actioned | `wontfix` |

Names are owner-approved. Remote label existence is not yet verified; this setup creates no remote labels. Check existing labels before using or creating any.

## docs/agents/domain.md

Single-context project. Read root `CONTEXT.md`, when present, and relevant `docs/adr/` records before domain or architecture work. The installed `/grill-with-docs` creates these lazily as terms and consequential decisions are agreed. Do not prepopulate them with unapproved hypotheses or implementation plans. `CONTEXT.md` is a glossary, not a specification. Use its agreed vocabulary and flag ADR conflicts. Before research or implementation proposals also read `docs/START_HERE.md`, the charter, protocol, open decisions and research synthesis. Current upstream renamed the glossary to `GLOSSARY.md`; retain the installed convention unless deliberately migrated. Research interventions remain separate versioned artifacts, never global project instructions.
