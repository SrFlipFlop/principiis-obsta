# Manual checkpoint review fixes — 2026-11-15

Scope: three reproduced P2 findings in manual evaluator provenance, interruption
allocation and suite Markdown. No model, generated application, remote service or
paid workload was run.

The public verification seams are `principiis.manual`, `principiis.suite report`
and `principiis.resource`, using real local fixture subprocesses. Existing approved
CLI seams remain unchanged except the required evaluator dependency manifest.
Tests follow the TDD skill and use persisted crash-state fixtures, never mocks of
controller internals.

The initial CLI test run failed (2 of 3) because the evaluator manifest argument
was unsupported. After implementation, the four manual CLI tests pass, covering
imported helper drift under the same evaluator version, a new version's rerun,
immutable primary evidence, a crash after durable allocation but before directory
creation, a legacy orphan with unknown original provenance, readable report links
and developer outcome, and evaluator argv-file drift during development resume.

The full 68-test suite passes with two existing skips. An intermediate full run
found an accidental variable replacement in token-usage deduplication; that change
was corrected and the full suite rerun successfully. No qualification or efficacy
claim follows from fixture tests.

The dependency manifest is an explicit author assertion of complete dependency
closure, not automated dependency discovery. Include wrappers/controller sources
and fixtures used by the command. External runtime/container identity still needs
to be frozen by the operator. Legacy orphan identities remain null; resource
inspection distinguishes their artifact paths without inventing historical IDs.
Three explicit development retries, manual checkpoint triggers and no model-stage
time limits remain the operational contract.
