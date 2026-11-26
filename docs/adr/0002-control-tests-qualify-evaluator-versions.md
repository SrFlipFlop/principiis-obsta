# Control tests qualify evaluator versions; the owner approves milestones

Accepted by the owner on 2026-11-26 during the simplification review (#62).

## Context

Each evaluator change needed the owner to sign off on its exact bundle hash. In #8 the owner approved one technical bundle; when #57 corrected false failures in that evaluator, the approval did not carry over to the corrected bytes, so #57 stayed open waiting for a second hash review even though its control tests already passed. That loop stalled work without adding evidence the controls did not already give.

## Decision

- An **evaluator version** (the hidden checks plus their declaration) is usable once its automated control tests pass: safe, property-violating, reject-all/broken and alternative-valid implementations, plus repeats that show the checks are not flaky.
- The owner approves milestones, such as "start comparing conditions", not individual evaluator versions or bundle hashes.
- Evaluator versions stay hash-identified and are recorded with every score. A changed evaluator is a new version, and the affected snapshots are rescored consistently across conditions (`derive-evaluation` does this for retained runs).

This keeps [ADR 0001](0001-separate-baseline-requests-from-security-expectations.md): request and property changes still produce new versions with consistent evaluation. Only the per-version owner sign-off goes away.

## Consequences

- The `owner_review` and `qualification_status` strings in a benchmark `package.json` will be replaced by `qualified_through: <int>`, the last step whose evaluator passed its controls. That code change belongs to the benchmark-package issue (#68).
- Control results are kept with the evaluator version they qualify, so anyone can check why a version was usable.
- #57 closes: its fix is the corrected evaluator used by #44, which passed its controls.
