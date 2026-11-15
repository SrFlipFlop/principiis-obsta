# Suite execution and reporting

Issue #18 adds `python3 -m principiis.suite`. It composes the existing sequence,
resume, resource and independent-evaluation artifact interfaces. It has no benchmark
folder or edition assumptions and adds no dependencies. It does not launch a run
unless `run` is explicitly invoked.

A controller-only manifest selects already-bound sequence manifests:

```json
{
  "id": "local-baseline",
  "version": "1",
  "applications": [
    {"id": "portal", "sequence": "/local/controller/portal/sequence.json"},
    {"id": "support", "sequence": "/local/controller/support/sequence.json"}
  ]
}
```

Paths resolve relative to the suite manifest. Applications have unique, safe IDs.
Use fixture executors for engineering checks; actual model execution remains subject
to the approved specification and execution-time readiness gate.

```sh
python3 -m principiis.suite run --suite /local/suite.json \
  --application portal --executor '["python3", "/local/fixture-executor.py"]' \
  --output /local/suite-artifacts
python3 -m principiis.suite run --suite /local/suite.json \
  --application support --executor '["python3", "/local/fixture-executor.py"]' \
  --output /local/suite-artifacts --resume
python3 -m principiis.suite report --output /local/suite-artifacts --format markdown
```

Repeat `--application` to select several applications; omit it for all applications.
`--codex-config` replaces `--executor` using the existing ordinary Codex path.
Selection never changes task content or supplies suite metadata to the writer.
Each application retains its own run identity, fresh sessions and independent files.

Continuation requires `--resume`. Completed checkpoints are not regenerated.
Incomplete attempts require the additional `--retry-incomplete`; retry creates a new
attempt from the last completed snapshot. Controller errors are retained separately,
and do not prevent other selected applications from being attempted. Suite/sequence
manifest changes reject continuation; existing sequence fingerprints also protect
requests, check files and execution configuration. A changed experiment needs a new
run. Changes to unchecked transitive evaluator dependencies still require operator
version discipline, as in the existing sequence interface.

Run a revised evaluator without invoking a writer:

```sh
python3 -m principiis.suite evaluate --output /local/suite-artifacts \
  --application portal --evaluator-version oracle-2
```

This assesses every completed retained attempt of the selected applications. It
uses each retained task's check argv, records current check-file hashes and the
explicit evaluator version, copies the immutable snapshot into a temporary check
workspace, and appends separate assessment/log/resource artifacts. The original
primary scores and sequence history remain unchanged. Apply a revised oracle to all
affected snapshots for consistent rescoring; the report deliberately does not choose
one rerun as replacement ground truth. An evaluator failure remains unassessable.
The check command is trusted controller code: generated applications must continue
to run through the restricted evaluator, never directly on the host.

The report includes all application identities/conditions, sequence fingerprints,
primary attempts and failures, planned/completed/unstarted checkpoint denominators,
security assessability, controller errors and separate versioned assessments. A
completed failed checkpoint counts as completed work, not a security pass. Retry
attempts remain separate observations; they do not expand the planned denominator.

Existing `resource.inspect` reconciles unique development/evaluation sessions and
preserves measurement scope, tokens, memory and unknown costs. Rerun resources are
separate and never counted as fresh development. Existing independent investigations
can be stored under `applications/<id>/investigations/<name>/`; their
`investigation.json`, agent record and referenced tool measurements are included.
Their outer elapsed duration already includes agent/tool time: do not sum it again
with the component durations. Claims retain verified/rejected/unresolved status from
the independent investigation stage. Verified root causes are deduplicated within an
application across checkpoints/investigations; equal labels in different applications
are separate. Findings remain exploratory and never change primary scores.

Checkpoints are dependent, single runs do not estimate stochastic reliability,
application/stack effects are bundled, and this reporting makes no efficacy claim.
Reports contain evaluator information and belong outside evaluated development
contexts. They are local research artifacts, not sanitized public releases.

Verification:

```sh
python3 -m unittest discover -s tests -p test_suite_cli.py -v
python3 -m unittest discover -s tests -q
```

The six initial CLI tests failed because the suite command did not exist. Passing
behavioral tests cover partial selection/continuation, retained explicit retries,
unknown security, candidate versus evaluator failures, changed-manifest rejection,
versioned evaluator-only reruns and application-scoped root-cause deduplication.
An additional regression failed when a candidate wrote its own `result.json`: resource
inspection now accepts explicitly selected controller artifact paths, excluding all
candidate files. No model, generated application, paid call or pilot is used in
these tests.

Independent review identified three additional failure paths: SIGTERM bypassing
child cleanup, Codex configuration errors preceding retained error handling, and
missing retained task metadata aborting evaluator reruns. Three behavioral
regressions failed before the corrections. SIGTERM now uses the existing controller
interruption path, retaining measurements and terminating the child process group;
no further application is launched after that signal. Executor preparation errors
are retained per application. Evaluator preparation failures create unassessable
assessment records and allow the remaining retained checkpoints to be assessed.

A further two-step regression reproduced SIGTERM during the first primary evaluator:
although execution retained its final measurements, the sequence began another writer.
The suite now propagates its stop callback to checkpoint boundaries. A completed
snapshot and interrupted evaluator result remain completed checkpoint evidence;
the sequence status becomes `interrupted`, no next writer/application starts, and
the command exits 130. Explicit `--resume` continues from that checkpoint. SIGINT
uses the same stop path. This does not recover a live session or silently retry it.
The regression failed before the fix and passes with all 11 suite CLI tests.
The complete local suite passed 60 tests (two environment-dependent skips).
