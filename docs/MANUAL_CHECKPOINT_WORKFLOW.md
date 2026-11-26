# Manual checkpoint operation

The current operator path is the [baseline command sequence](../README.md#baseline-command-sequence).
[HITL issue #38](https://github.com/SrFlipFlop/principiis-obsta/issues/38) (closed) holds the
earlier walkthrough findings.

The owner's 2026-11-15 settings select ordinary subscription Codex, harness defaults,
no model-stage timeout, and at most three explicit additional development attempts.
Commands below are legacy operator instructions; they are not baseline developer prompt additions.

`python3 -m principiis.manual develop` runs exactly one selected next checkpoint.
Each attempt starts a fresh session from the last completed developer snapshot,
with cumulative requests but no earlier conversation, future requests, checks or
results in its prompt. Successful development preserves a verified snapshot and
`pending_evaluation` result; it never launches evaluation. Candidate failures found
by evaluation do not reopen development. Continue with the next checkpoint.

Provision the clean subscription-authenticated Codex runtime separately as described
in the existing runtime documentation. Do not copy the research account's skills,
instructions, session memory or credentials into generated projects. In the ordinary
Codex configuration set `model` and `reasoning_effort` to the literal `"default"`.
The adapter omits both overrides and records effective values as unknown when not
exposed, retaining requested settings and executable version. Other explicit runtime
configuration fields remain required. No authentication or account changes occur.

Initialize a suite without executing agents, then develop one application checkpoint:

```bash
python3 -m principiis.suite prepare --suite /operator/tasks/suite.json --output /operator/runs/baseline
python3 -m principiis.manual develop --sequence /operator/tasks/document-portal/sequence.json --step step-01 --codex-config /operator/codex.json --output /operator/runs/baseline/applications/document-portal
```

Use the actual versioned step IDs and suite application IDs. Output must remain
outside the research/task trees and researcher instruction ancestors. Only run one
controller command against an application output directory at a time.

Trigger the predefined primary evaluation separately:

```bash
python3 -m principiis.manual evaluate --step step-01 --evaluator-version portal-oracle-v1 --evaluator-manifest /operator/evaluators/portal/manifest.json --output /operator/runs/baseline/applications/document-portal
python3 -m principiis.suite report --output /operator/runs/baseline --format markdown
python3 -m principiis.resource /operator/runs/baseline/applications/document-portal --format markdown
```

The first explicit evaluation is `evaluations/step-01/1/result.json`, role `primary`,
including errors. Later invocations append role `rerun`, with evaluator version,
command/file hashes and developer-result/snapshot-manifest hashes. Evaluation requires
an operator-authored JSON dependency manifest, for example:

```json
{"version":"portal-oracle-v1","complete":true,"files":{"check.py":"<sha256>","policy.py":"<sha256>"}}
```

`complete: true` explicitly declares the full evaluator artifact/dependency closure,
including imported helpers, fixtures, wrappers and controller sources that affect the
checks. Paths are relative to the manifest directory and must stay within it. Each
file is verified before allocation; command file arguments must be included. This is
an author declaration, not an import scanner: the controller cannot discover an
omitted runtime dependency. Freeze external runtime/container versions separately.
The executable digest (when its argv path is a file), manifest digest and declared
file digests are preserved in provenance. Missing/incomplete manifests fail closed.
Changing a helper requires updated hashes **and a new evaluator version**, even if
the entry point is unchanged. Development pins evaluator argv-file contents in its
run fingerprint; dependency-closure provenance is declared separately before the
first manual assessment, never injected into development context. Changed evaluator
content requires a new version. Nothing rewrites the developer result or historical
assessment. A durable allocation ledger records identity and provenance before an
evaluation directory is created. The next evaluation reconciles interrupted
allocations into explicit error evidence under their original primary/rerun role.
Legacy orphan directories without a ledger become error evidence with unknown
identity/provenance; their files are retained and never assigned current provenance.
Suite reports explicitly link the first primary assessment and retain
the original developer outcome; later reruns remain separate. Resource inspection
includes retained attempts and separates development from evaluation. Missing token
categories, hosted memory and subscription spending stay unknown.

An incomplete developer process leaves workspace/log/resource evidence. Reissue the
same `develop` command with `--retry` to start a separate attempt from the prior
completed checkpoint, discarding incomplete files from the next workspace while
retaining their original artifacts. Without `--retry` it refuses; after four total
attempts it refuses further retries. Successful development cannot be retried within
the same run. SIGTERM/SIGINT retain measured interruption evidence; after an abrupt
controller death the next command reconciles a completed result or requires retry.

Explicitly develop `--step step-02` using the same sequence/config/output to advance.
There is no implicit evaluation, next step or automatic retry. Legacy `principiis
sequence` and `principiis.suite run` retain their earlier automatic behavior for
compatibility and are not the owner's manual execution workflow.

Independent supplemental investigation is separately triggered with
`python3 -m principiis.investigation`. Its config may use `codex_config` (path to the
ordinary Codex configuration) instead of fixture `agent` argv, and
`timeout_seconds: null`. Keep its prompt, output and evidence hidden from development.
Raw redacted Codex JSONL stays in `agent.stdout`; the final agent message is separately
saved as `agent.final.txt` and parsed as a JSON object with a `claims` array. The agent
receives the predefined evaluator prompt as ordinary text. Claims remain unresolved
without operator-declared reproducible evidence; agent claims never change primary
scores. Restricted application-check bounds remain diagnostic/runtime constraints,
not developer or evaluator model time budgets.

Engineering verification uses fake executable Codex streams and real fixture
processes only; no live model/pilot run is necessary:

```bash
python3 -m unittest discover -s tests -p test_manual_cli.py
python3 -m unittest discover -s tests -p test_codex_cli.py
python3 -m unittest discover -s tests -p test_investigation_cli.py
```

The tests exercise manual development, first primary evaluation, retained reruns,
cumulative next-step requests, reporting, interrupted processes, usage retention,
retry exhaustion, harness defaults and separate final-message parsing. Installed
Codex help/version was inspected locally (0.169.0, 2026-11-15); runtime/oracle
qualification and an actual approved subscription trial remain separate work.
