# Portal development commands (#40–#42)

Implemented foundations, 2026-11-16. This composes the existing manual checkpoint
controller; it does not introduce another execution engine. Scope and execution
settings are in [PROJECT.md](../../PROJECT.md). Milestone 1 was accepted live under
#40–#42; regression fixtures are not live acceptance evidence. See the [implementation
verification record](../archive/reviews/MVP_1_IMPLEMENTATION.md).

From this checkout, inspect `python3 -m principiis --help`. Commands use the Python
standard library. Initialize a reusable run outside the research checkout and outside
directories with researcher instruction/configuration ancestors:

```bash
export PRINCIPIIS_RUNS_ROOT=/operator/principiis-runs
python3 -m principiis init --application document-portal --run portal-first \
  --runtime-config /operator/development-runtime.json
python3 -m principiis status --run portal-first
```

`--runs-root PATH` overrides the environment variable. The default is
`~/.local/share/principiis/runs`. Run names are single path components. Initialization
validates configuration and hashes the real released requests against the portal
package, then freezes requests 1–3 and the development runtime settings. It invokes
neither Docker nor a model. Existing run names are rejected. Malformed configuration
does not allocate a development attempt. The runtime configuration format, image
preparation and review requirements are in [Development runtime and
preview](DEVELOPMENT_RUNTIME.md).

The saved `configuration.json` identifies a **development rehearsal**. For a scored
three-step rehearsal, pass `--evaluator-manifest PATH` at `init` to bind the qualified
hidden checks immediately. An unbound rehearsal can develop code but cannot evaluate
it; create a new run with the evaluator manifest to score checkpoints. The ten-step
package remains unqualified. See the [MVP evaluation CLI](MVP_EVALUATION_CLI.md).

The owner manually starts one development action by running the selected command:

```bash
python3 -m principiis develop --run portal-first --step 1
python3 -m principiis status --run portal-first
```

The command itself is the operator action. The controller saves the selected step,
attempt and result; no approval file is required or sent to the coding agent.
The runtime checks for subscription authentication without saving the raw login
status. It never supplies API keys or overrides default model/reasoning settings.

One command starts one fresh Codex session. There is no model-stage time limit and
no automatic evaluation, next development step, retry or candidate repair. Requests
2 and 3 are separately triggered with `--step 2` and `--step 3`. The controller copies
the preceding completed snapshot, retaining project files and agent-written notes,
and sends requests cumulatively through the selected step. Only the current
workspace and separately provisioned subscription authentication are mounted in the
development container. Future requests, prior conversations, researcher instructions,
hidden tests and results remain outside that boundary.

Successful generation records `pending_evaluation` and preserves a content-verified
snapshot. This status describes development completion, not a functionality or
security pass. Candidate functionality may be broken; keep that outcome. Completed
development cannot be replayed in the same run to obtain a different application.
Out-of-order selection and missing/corrupted prior checkpoints are rejected.

Status reports `wait` while an operator action holds the per-run lock. Competing
development, preview and cleanup commands are rejected, preserving allocation
history. Read-only inspection remains available with explicitly partial measurements.
Do not mix the legacy manual CLI with concurrent operator commands.

An incomplete attempt retains its workspace, logs and exposed measurements. Use an
explicit retry, for example in a separately named recovery run:

```bash
python3 -m principiis develop --run portal-recovery --step 2 --retry
```

Retries start from the last completed snapshot, excluding partial edits from the
incomplete attempt. Each attempt keeps a distinct session identity and artifact
directory. There are at most three additional retries per checkpoint. SIGINT/SIGTERM
are retained as controller interruptions. An abruptly killed controller can leave
incomplete allocation evidence and an orphan runtime. Status names the retained
allocation and blocks further development until explicit cleanup:

```bash
python3 -m principiis cleanup --run portal-recovery --step 2
```

Cleanup removes the identified development container without a model call and saves
separate evidence; original sidecars and results remain unchanged. A failed cleanup
stays blocked. Logs/usage emitted after an abrupt controller death may be unavailable.
A missing completed result or changed snapshot
is an integrity error, rather than permission to regenerate a completed checkpoint.
Changing frozen request/runtime configuration requires a new identified run.

Preview a completed checkpoint using separately versioned startup configuration:

```bash
python3 -m principiis preview --run portal-first --step 1 \
  --preview-config /operator/portal-preview.json
python3 -m principiis preview --run portal-first --step 1 --stop
```

The command prints the local URL, status, evidence path and cleanup command. A preview
uses a disposable copy and a prepared image with the candidate's dependencies. It
never executes application code on the controller host. A trusted TCP relay forwards
only to the application port; the application remains on its isolated internal
network. The retained snapshot stays
unchanged. Startup errors and logs remain evidence. Stopping removes all previews
for that checkpoint; copies/logs remain. An HTTP-200 readiness response is not a test
of the complete portal workflow: record actual browser observations separately.

Inspect or save the evidence:

```bash
python3 -m principiis status --run portal-first --format json
python3 -m principiis report --run portal-first --format markdown
python3 -m principiis report --run portal-first --format csv
```

Each `report` saves all three formats under the run's `reports/` directory:
`development.json`, `development.csv` and `development.md`. These derived reports can
be regenerated; original attempt records are never rewritten by reporting. JSON
includes per-checkpoint source/snapshot identity/log references, preview references,
every retained attempt and resource totals. CSV has one row per attempt with source,
session, outcome, timestamps, development duration, token categories and scoped memory.
The readable report includes the next permissible action and artifact locations.

Active development duration is the sum of measured stages; wall elapsed time spans
their timestamps and includes idle gaps. Cache input and reasoning output are subsets
of input/output, not extra tokens. Unknown categories remain unknown through totals.
Host Docker-client sampled RSS and container sampled working-set memory are separate
measurements. Hosted model memory, subscription spending and API-equivalent spending
are unknown. Reports select canonical journal allocations; candidate-created JSON
files cannot become accounting records. Each run is exported separately, so the
requests-1–3 run and recovery run are never pooled or counted as one sequence.

Exit zero means the command recorded or inspected an outcome. Read the retained
status: incomplete generation or a failed preview is still a recorded outcome.
Configuration/selection/integrity errors exit nonzero. A cleanup failure remains
explicit evidence and must not erase the observed process exit status.

The [runtime fix controls](../archive/reviews/MVP_1_RUNTIME_FIXES.md) exercise nested
workspace-write sandboxing and retained Python virtual environments on the local
Docker host. Interpreter links are bound to the exact development image; preview
must use that same image and can launch `.venv/bin/python app.py` when the candidate
uses that environment. Arbitrary external links remain unsupported. Actual
subscription access, image/access review, generated-application dependencies and
restricted browser acceptance remain separate live qualification work. Preserve
failures instead of regenerating a completed candidate.

The subsequent [#41–#42 qualification](../archive/reviews/ISSUES_41_42_LIVE_QUALIFICATION_20261117.md)
records actual requests 2–3, restricted generated-portal browser previews, a separately
identified real interruption/explicit retry and reconciled per-run exports. The owner
walkthrough and acceptance are recorded there. Hidden evaluation remains
unbound; these development observations do not supply primary scores.
