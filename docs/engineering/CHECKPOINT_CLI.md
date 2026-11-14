# Fixture checkpoint interface (#1)

Implementation decision (2026-11-14): use Python 3.10+ and its standard library, JSON task/results and local filesystem artifacts. This keeps the first vertical slice runnable without dependency installation, a database, services or a plugin framework. It is engineering scaffolding, not a research finding or a new benchmark application.

From the repository root, one command runs the harmless fixture without any model:

```sh
python3 -m principiis run --task fixtures/engineering/task.json --executor '["python3", "'"$PWD"'/fixtures/engineering/executor.py", "pass"]' --output /tmp/principiis-fixture-run
```

Choose a new output directory for each invocation. Existing output directories are rejected, so evidence is never silently replaced. The command exits zero once an attempt has been recorded; inspect `result.json` for the scientific outcome. Argument/configuration errors exit nonzero. This convention allows later sequence execution to continue after scored candidate failures without treating them as controller crashes.

Run behavioral verification with `python3 -m unittest discover -s tests -v`.

## Task author contract

A task JSON file contains:

```json
{
  "id": "engineering-greeting",
  "version": "1",
  "condition": {"id": "ordinary", "version": "1"},
  "request": "request.txt",
  "check": ["python3", "check.py"]
}
```

`request` is a UTF-8 visible task file, relative to the task JSON (absolute paths also work). Only its contents are delivered to the executor. `check` is hidden evaluator argv, never shell text. Existing file arguments relative to the task JSON are resolved to absolute paths before evaluation. Use absolute paths for executable/check arguments when there could be ambiguity. This format is for one checkpoint; sequence validation and cumulative requirement semantics belong to #2.

## Executor subprocess contract (#2/#3 seam)

`--executor` is a JSON array of argv strings. The controller starts one fresh subprocess with an empty application workspace as cwd, sends only visible request text on stdin, and captures stdout/stderr separately. The executor writes application files into cwd. Exit zero declares the candidate complete; nonzero, launch failure or controller interruption gives `incomplete`, retaining partial files/logs without scoring or creating a completed snapshot. No live session recovery or implicit retry is provided.

The supplied executor is a trusted deterministic test double; it asserts exact visible stdin and an initially empty project. It has modes `pass`, `fail`, `evaluator-error`, `malformed` and `incomplete`. The latter modes exercise evidence handling and are not benchmark task instructions. No evaluator scores are returned to the executor. The task manifest, check code, reports and researcher documents are outside the development workspace and absent from stdin/argv. Prior conversations are not supplied.

**This fixture path is not an OS sandbox.** Trusted subprocesses inherit the normal environment and can access host paths, including parents of cwd. It does not claim to stop malicious code or a real agent from searching outside its workspace. Enforcing the actual coding-agent context boundary belongs to #3; restricting generated application/evaluator execution belongs to #6. Do not use this host subprocess path for untrusted applications. The fixture's closed-file-set check is a harmless security-property-shaped control, not evidence about application security.

## Independent evaluator subprocess contract (#6 seam)

After successful executor exit, `snapshot/` is a recoverable copy of its application files, preserving symlinks. The evaluator gets another temporary copy as cwd, so ordinary evaluator writes cannot change the retained checkpoint. It receives no stdin request or development transcript. Check code stays outside these directories. The temporary copy is deleted after evaluation; retained evaluator stdout/stderr stay in the run artifacts. This filesystem copy does not restrict host access, network or privileges.

On exit zero the check must emit one JSON object on stdout:

```json
{"functional": "pass", "security": "pass"}
```

Each value must be `pass`, `fail` or `unassessable`. Additional fields are ignored. Both pass gives `joint_pass`; any fail gives `candidate_failure`; otherwise the outcome is `unassessable`. Nonzero exit, missing executable, malformed JSON or invalid score values gives `evaluator_error`, with both score fields remaining `unknown`. Errors are never silently converted into candidate failure or pass. Evaluator launch errors have null exit status and an error message; a started evaluator retains its stdout/stderr even when parsing fails.

#6 can replace host evaluation with its restricted browser/backend runner while retaining this score/result boundary. Real benchmark security properties and oracle qualification are not supplied by this engineering fixture.

## Artifacts and identity

Each output directory holds:

- `request.txt`: the delivered visible request, outside the application workspace.
- `workspace/`: application files, including partial output on incomplete attempts.
- `snapshot/`: completed, recoverable checkpoint; never edited by the controller/evaluator after creation. It is not an OS-enforced immutable archive.
- `executor.stdout` / `executor.stderr`: executor output, independent of evaluator output.
- `evaluator.stdout` / `evaluator.stderr`: started evaluator evidence, when available.
- `result.json`: schema version, fresh run UUID, task and condition IDs/versions, attempt number, checkpoint ID, outcome, scores, resolved subprocess commands, exit statuses, errors and separate elapsed stage durations.
- `report.md`: readable identity and primary scores/outcome.

The single-task attempt is number 1; checkpoint ID equals task ID. Later resume/sequence work must preserve identity and evidence rather than overwrite them. Initial `incomplete` evidence is written before executor launch; the result is updated at stage boundaries. Explicit handling covers executor/evaluator launch failures and interrupts caught by Python. Hard process termination, power-loss durability, process-tree cleanup, retry policy, tokens/memory/cost accounting and transactional artifact writes remain later tickets. Missing measurements are not estimates of zero.

## Verification record

Tests use the CLI/artifact and subprocess contracts, with real local subprocesses. Red-before-green cycles observed: missing CLI; evaluator exception incorrectly crashed controller; incomplete executor was wrongly scored; missing executor/check executable raised without a final result. Each was fixed before the next slice. Passing tests also cover candidate failure retention, malformed evaluator output and evaluator mutation of its disposable copy. No models, paid calls or benchmark applications were executed.

## Incremental sequence interface (#2)

Run an ordered manifest with a trusted fixture executor:

```sh
python3 -m principiis sequence --sequence /path/to/sequence.json --executor '["python3", "/absolute/path/to/executor.py"]' --output /tmp/new-sequence-run
```

A sequence manifest defines `id`, `version`, `condition` (the same identity object as a single task), and a nonempty ordered `steps` array. Each step defines `id`, `version`, `sequence_version`, `request`, and `check` as in the single-task format. `sequence_version` must equal the enclosing version. IDs must be unique single path components. Request/check file paths resolve relative to the sequence manifest. All steps and request files are validated before creating a run or invoking an executor.

Every step starts a new executor subprocess and records a fresh `session_id`; all checkpoints share the sequence `run_id`. The initial application workspace is empty. Later workspaces copy the previous completed snapshot, including agent-written notes and instructions. Stdin concatenates only requests through the current step, in chronological order separated by two newlines. Request authors must state changes/supersession explicitly: earlier requests remain visible as history. No prior stdout/stderr/conversation, external session state or evaluator output is copied into the workspace or stdin. Future requests remain outside the delivered context.

The output root contains `sequence.json` with sequence identity, ordered checkpoint outcomes/artifact links and `running`, `completed` or `incomplete` status. Each `steps/<id>/` directory uses the single-checkpoint artifact contract; `tasks/` holds resolved controller metadata outside development workspaces. A completed candidate advances even after functional/security failure, unassessable scoring or evaluator error. Retained historical outcomes/snapshots remain intact. An incomplete executor stops the sequence with its partial files and evidence retained. Resume/retry and hard-termination recovery remain #4 scope. A different run requires a new output root and starts empty.

The trusted host fixture limitation above applies equally here: absence from delivered stdin/workspace is tested, but host filesystem discovery is not prevented. This command is scaffolding for deterministic fixtures, not the real Codex context-isolation path (#3).

Verification: `tests/test_sequence_cli.py` checks a failing-then-passing sequence twice with real subprocesses, notes/code persistence, distinct process and session identities, exact cumulative requirements, a future-request sentinel, original snapshot retention and invalid-manifest rejection before artifacts. Red-before-green evidence: missing `sequence` CLI failed first; missing condition validation then created an artifact directory before failing, fixed by preflight validation. No live agent or model was invoked.

## Ordinary Codex adapter (#3)

`run` and `sequence` accept `--codex-config /absolute/path/config.json` instead of `--executor`. This selects ordinary `codex exec`, one fresh invocation per step. This is an execution capability, **not authorization to launch the pilot**. Tests use a fake executable only. Example configuration (model is a placeholder, not a selected pilot model):

```json
{
  "executable": "/absolute/path/to/codex",
  "codex_home": "/outside/research/clean-existing-codex-home",
  "model": "SELECT-AT-EXECUTION",
  "reasoning_effort": "medium",
  "sandbox": "workspace-write",
  "approval_policy": "never",
  "network_access": true,
  "web_search": "live",
  "clean_runtime_review": "Record operator review/date and runtime provenance here"
}
```

Use a separately provisioned ordinary runtime with existing subscription authentication, installed toolchains and no researcher global instructions, skills, hooks, managed prompt additions or external memories. The adapter does not log in/out, inspect/copy credentials, change account settings or verify subscription identity; `authentication_verified` is unknown. No API-key or provider override environment is inherited. Do not point this at the researcher's usual CODEX_HOME: visible instruction/skill/hook/session-memory locations are rejected. Existing credentials remain owned by Codex, whose normal token refresh may update its store during an authorized future run. The implementation and tests do not access credentials. The adapter avoids `forced_login_method`: mismatched credentials may cause Codex to log out, violating the intended no-authentication-change workflow. Subscription identity remains an operator prerequisite for launch readiness (#19).

The configuration must explicitly select every setting. The adapter records its actual `--version` response, selected model, exact launch argv, supported configuration overrides, declared runtime review, intended access mode, exit status and elapsed time. It supplies `--no-daemon`, `--ephemeral`, `--ignore-user-config`, `--ignore-rules`, JSON events and a new empty HOME per step; CODEX_HOME remains the explicitly supplied clean runtime. It does not resume conversations or insert instructions. Built-in ordinary tools remain available, shell network access and web search are selected explicitly, and dependency installation is possible under normal workspace-write permissions. `approval_policy=never` returns permission failures to Codex; choose/review the actual normal approval policy at execution time. This adapter does not claim to reproduce arbitrary personal user configurations; the ordinary runtime setup must be reviewed and kept fixed across comparisons.

Output under the research checkout, output that encloses the task package, and output with instruction/config ancestors are rejected before creating artifacts. These checks prevent common accidental context loading; they are **not a filesystem isolation boundary**. Under normal Codex permissions, host reads can still discover sibling task files, evaluator materials, artifacts and the research checkout. For a real run, provision the ordinary runtime on a separate host/container/filesystem account where those materials are absent or inaccessible, with the same intended normal tools/network access. The clean-runtime review records that operational boundary. A review string alone does not enforce it. The tests verify delivered context and configuration, not resistance to hostile host traversal. Do not put secrets or hidden materials in accessible host locations and then treat this adapter as containment. Agent-authored project instructions/notes persist normally.

JSONL stdout retains exposed command, file/tool events, summaries and usage; stderr is separate. Recognizable JSON credential fields, bearer values and `sk-` keys are redacted before writing logs. No credential/environment dump is created. Redaction cannot recognize arbitrary secrets embedded in free text or application files: the reviewed runtime/tasks must contain no production secrets. Reported usage and hosted-model memory stay unknown in result metadata; the original exposed usage events remain available for the resource-accounting ticket. Logs stream to disk, including failed/partial attempts; nonzero exit preserves partial files and never triggers evaluation or implicit retry.

Verified 2026-11-14 against installed `codex-cli 0.169.0` local `--help` / `exec --help` (read-only, no model invocation) and [official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference). Current flag support is a local observation; compatibility with other versions and the operator's subscription runtime must be rechecked before execution. No actual model, billing, credential or production-runtime behavior was tested.

TDD evidence: CLI first failed because `--codex-config` was absent; the second slice failed because credential-shaped events were retained. Fake executable contract tests now cover two fresh sequence invocations, cumulative/current requirements with a future sentinel, retained notes, explicit model/permissions, no inherited API key, passive events/stderr, nonzero exit/partial files, credential redaction and contaminated-home rejection. Run `python3 -m unittest discover -s tests -v`.

## Checkpoint resume and explicit retry (#5)

Repeat the same `sequence` command and add `--resume`. A completed sequence is a no-op. A sequence interrupted during a step requires `--resume --retry-incomplete`; this is one explicit new attempt, never an automatic retry loop. Failed functional/security candidates and evaluator errors are completed development checkpoints and remain eligible as the next step's starting state. A nonzero/interrupted development executor remains incomplete and is never scored.

The sequence journal is written before each launch and atomically replaced at stage boundaries. The journal records an active attempt before executor launch, allowing a later resume to classify a hard controller termination conservatively as incomplete. Existing attempt files are never rewritten during recovery. SIGTERM and SIGINT are handled as controller interruptions; subprocess cleanup and retained execution measurements use the measured executor boundary. SIGKILL/power loss cannot promise cleanup or final measurements: the last durable artifacts and active journal record remain the evidence, and retry still needs an explicit request. No live Codex conversation is recovered.

Attempt one keeps `steps/<id>/`; subsequent attempts use `attempts/<id>/<number>/`. Results retain the sequence run ID but receive distinct session IDs and attempt numbers. A retry copies only the last completed snapshot (including a failed candidate), or starts empty when no checkpoint completed. Partial files, logs and resource records stay in the original attempt. Evaluator output never enters the next workspace. The journal includes historical incomplete records as well as completed outcomes.

Resume requires an identical manifest, visible request contents, check-file contents and selected executor configuration (including Codex configuration and executable version). Content changes without a version bump are also rejected. Use a new output root for a deliberate new run; results are never implicitly pooled. This records declared runtime configuration, not a hash of the entire installed toolchain or remote dependencies. Do not concurrently operate on one output root.

Verification uses only real deterministic fixture subprocesses: initial missing resume flags failed red before implementation; retry then preserved every prior attempt file byte-for-byte, restored the failed checkpoint and created a fresh session. An interrupt test checks cleanup, distinct outcome classification, configuration rejection and retained evidence. No model was invoked.
