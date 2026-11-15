# Issue tracker — GitHub

Work items and new PRDs live in GitHub Issues for `SrFlipFlop/principiis-obsta`. The approved [baseline specification](../BASELINE_PILOT_SPEC.md) remains the scope authority; the [local issue breakdown](../planning/BASELINE_ISSUE_BREAKDOWN.md) records its original publication, not live completion status. Read the current issue body, comments and blockers before starting work. A work item does not silently amend the approved research scope.

Use `gh` from this checkout. Read tickets with `gh issue view <number> --comments`; list with `gh issue list`. If this installed `gh` fails on the deprecated Projects query, use `gh issue view <number> --json number,title,body,state,comments`. When the user or an explicitly invoked workflow authorizes publication, create the requested issue or PR. For multiline bodies write a temporary UTF-8 file and pass `--body-file`; preserve exact text. Keep hidden evaluator material and confidential data out of tickets.
