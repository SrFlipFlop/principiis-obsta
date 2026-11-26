# Manual checkpoint operation

The operator path is the [baseline command sequence](../README.md#baseline-command-sequence).
[HITL issue #38](https://github.com/SrFlipFlop/principiis-obsta/issues/38) (closed) holds the
earlier walkthrough findings.

The owner's 2026-11-15 settings select ordinary subscription Codex, harness defaults,
no model-stage timeout, and at most three explicit additional development attempts.
These are operator instructions; they are not baseline developer prompt additions.

`principiis develop --run <name> --step <id>` runs exactly one selected next checkpoint
in the isolated development runtime. Each attempt starts a fresh session from the last
completed developer snapshot, with cumulative requests but no earlier conversation,
future requests, checks or results in its prompt. Successful development preserves a
verified snapshot and `pending_evaluation` result; it never launches evaluation.
Candidate failures found by evaluation do not reopen development. Continue with the
next checkpoint.

Provision the clean subscription-authenticated Codex runtime separately as described
in the [runtime documentation](engineering/DEVELOPMENT_RUNTIME.md). Do not copy the
research account's skills, instructions, session memory or credentials into generated
projects. No authentication or account changes occur.

Hidden checks run only through `principiis evaluate --run <name> --step <id>` against a
bound, qualified evaluator release; see the [evaluation CLI](engineering/MVP_EVALUATION_CLI.md).
That command is the only writer of `development/evaluations/<step>/allocations.json`.

An incomplete developer process leaves workspace/log/resource evidence. Reissue the
same `develop` command with `--retry` to start a separate attempt from the prior
completed checkpoint, discarding incomplete files from the next workspace while
retaining their original artifacts. Without `--retry` it refuses; after four total
attempts it refuses further retries. Successful development cannot be retried within
the same run. SIGTERM/SIGINT retain measured interruption evidence; after an abrupt
controller death the next command reconciles a completed result or requires retry.
There is no implicit evaluation, next step or automatic retry.

The separate AI security review (`principiis evaluate --ai-review`) runs only in a
separately authenticated isolated reviewer runtime, with `timeout_seconds: null` and
`evidence: {}`; host agent or proof commands are rejected. Keep its prompt, output and
evidence hidden from development. Raw redacted Codex JSONL stays in `agent.stdout`; the
final agent message is saved as `agent.final.txt` and parsed as a JSON object with a
`claims` array. Claims remain unresolved and never change primary scores.

Engineering verification uses a fake Docker client and fixture processes only; no live
model run is necessary:

```bash
python3 -m unittest discover -s tests -p test_manual_rehearsal_cli.py
python3 -m unittest discover -s tests -p test_operator_development_cli.py
python3 -m unittest discover -s tests -p test_investigation_cli.py
```
