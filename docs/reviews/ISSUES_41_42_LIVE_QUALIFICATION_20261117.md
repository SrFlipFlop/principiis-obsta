# Issues #41–#42 — live continuation and recovery qualification, 2026-11-17

The owner instructed: “Great! Continue with #41 and #42.” The private authorization
records cover separately triggered portal requests 2–3 in the existing #40 run and a
separately identified interruption/retry qualification run. Existing subscription,
harness-default model/reasoning, fresh sessions and no development-stage timeout remain
unchanged. Implementation subagents were not used. No hidden evaluation or paid API
ran; retained development outcomes are `pending_evaluation`, not primary scores.

## #41: actual incremental development and usable previews

Run `portal-40-20261117-8b873374` continued from the completed request-1 snapshot.
Requests 2 and 3 were individually triggered with the operator command and the recorded
owner authorization. Each received the exact cumulative released requests through its
selected step. Container inspection confirmed only the current workspace and read-only
subscription authentication mounts, a read-only outer root, dropped capabilities and
ephemeral Codex with ignored external user configuration/rules. No previous session
history, future request or evaluator artifact was mounted. The three actual model
threads and controller session identities are distinct.

| Checkpoint | New session | Elapsed development seconds | Input tokens | Cached input subset | Output tokens | Reasoning subset | Input + output |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Request 2 | `b5fb1366-2d47-4b41-9688-98972def2c6f` | 211.226 | 405,905 | 361,600 | 7,441 | 446 | 413,346 |
| Request 3 | `91c79fe1-6278-4664-bbac-97112ee75945` | 181.749 | 311,945 | 271,488 | 5,968 | 214 | 317,913 |

Request 2's sampled container working set was 179,516,211 bytes and sampled host
Docker-client process-group RSS was 33,107,968 bytes. Request 3's respective values
were 217,160,089 and 33,120,256 bytes. Samples are scoped measurements, not guaranteed
peaks or hosted model memory. Effective model/reasoning and spending remain unknown.
Cached input and reasoning output are subsets, not extra billable token totals.
The original #40 Docker-start failure remains in the main run, with unknown usage;
therefore its all-attempt token aggregate remains unknown.

Request 2's sixteen positive API observations passed: accounts/login, collection
creation, reader membership/listing/download, role change, editor creation/editing,
identity-preserving moves into/out of a collection, and member removal. Chromium
rendered the populated collection and member controls with no observed page errors.
Request 3's fourteen positive API observations passed: literal case-insensitive note
search including `%` and `_`, empty search, export, archive/repeated archive, archive
listing, exclusion from active search, owner download, restore and exact bytes.
Chromium used the actual search form and archive link and rendered the retained data.
A supplementary browser action selected two documents and downloaded the generated ZIP.
A separate ZIP check confirmed two actual `note.txt` filenames remain distinct entries,
with correct manifest references and exact original bytes.

The initial request-3 smoke's duplicate-filename label was inaccurate: its note used
`note.txt` while its upload used `handover.txt`. That observation and the correction
remain retained. The supplementary check used actual duplicate filenames. No candidate
source was changed or generation replayed to improve these observations.

The retained source and manifests for all three checkpoints validate. Request 1's
original result, manifest and logs match its prior archive byte-for-byte. Request 2's
manifest is `0075e3e7d7d39b0f70f5df80aedf55f1b6d66dd2b6013b89440b816b3f494d9a`;
request 3's is `8106daf003f792c7e7304ccb7cf70ada2b285a5d98f9253759e1628fe1e799d4`.
Previews use disposable copies. These positive observations demonstrate a usable
preview path; full functional/security, upgrade and regression assessment remains
milestone-2 work. Candidate-owned tests and smoke observations do not qualify the
hidden oracle.

The latest preview is **http://127.0.0.1:32769**. Register a synthetic account to inspect
it. The separately retained request-2 preview is **http://127.0.0.1:32768**. Preview
URLs describe this session's running containers; inspect current status after a host
restart. Cleanup commands:

```bash
python3 -m principiis preview --run portal-40-20261117-8b873374 \
  --runs-root /var/tmp/principiis-live-runs --step 3 --stop
python3 -m principiis preview --run portal-40-20261117-8b873374 \
  --runs-root /var/tmp/principiis-live-runs --step 2 --stop
```

## Commands and evidence boundaries

```bash
python3 -m principiis develop --run portal-40-20261117-8b873374 \
  --runs-root /var/tmp/principiis-live-runs --step 2 \
  --authorization private/live/portal-40-20261117-8b873374/authorization-41.md
python3 -m principiis develop --run portal-40-20261117-8b873374 \
  --runs-root /var/tmp/principiis-live-runs --step 3 \
  --authorization private/live/portal-40-20261117-8b873374/authorization-41.md
```

Controller source at launch: Git `7048bde5da797e0af2d052291a9096ab037a92cc`.
No production controller code changes were needed for this continuation. The frozen
runtime uses Codex CLI 0.169.0 and development image
`sha256:848b627634e2a1c082949371cc36b41b704af7e7863ccb1c8dff441d0e0f9048`.
Owner authorization, operational scripts, boundary inspection, original observations
and derived audits remain ignored private/local artifacts. Credentials are excluded
from archives and public documentation.

## #42: planned actual interruption and explicit recovery

Separate run `portal-42-recovery-20261117-d5170b18` started request 1 from an empty
workspace and preserved its completed snapshot. It did not inherit the main run's
application. The planned exercise then launched request 2 separately. A passive
observer waited for actual Codex tool activity and changed source, observed edits to
`app.py`, saved workspace/file hashes and sent SIGTERM to that identified controller.
This was an intentional recovery exercise, not a development-stage time limit.

The interrupted attempt retained its partial workspace, exposed event logs, separate
session identity and `incomplete` status with `controller interrupted` evidence.
Measured development time was 73.001 seconds. Sampled host Docker-client RSS was
33,083,392 bytes and container working set was 93,784,637 bytes. No `turn.completed`
usage event was emitted; usage remains unknown. The development container was removed
and cleanup evidence retained. No costs or partial files were discarded.

One explicit retry was launched with `--retry` and the same scoped authorization.
A passive observer inventoried its workspace after the runtime allocation sidecar was
written and before Docker/model execution. Its files exactly matched the completed
request-1 snapshot, including retained agent-authored files, and differed from the
interrupted workspace. The retry received the same cumulative requests, a distinct
controller session and a fresh Codex thread/home. No operator edit or extra developer
instruction was used to force the restore result.

```bash
python3 -m principiis init --application document-portal \
  --run portal-42-recovery-20261117-d5170b18 --runs-root /var/tmp/principiis-live-runs \
  --runtime-config private/live/portal-42-recovery-20261117-d5170b18/runtime.json
python3 -m principiis develop --run portal-42-recovery-20261117-d5170b18 \
  --runs-root /var/tmp/principiis-live-runs --step 1 \
  --authorization private/live/portal-42-recovery-20261117-d5170b18/authorization.md
python3 -m principiis develop --run portal-42-recovery-20261117-d5170b18 \
  --runs-root /var/tmp/principiis-live-runs --step 2 \
  --authorization private/live/portal-42-recovery-20261117-d5170b18/authorization.md
# The planned observer sends SIGTERM only after actual source changes.
python3 -m principiis develop --run portal-42-recovery-20261117-d5170b18 \
  --runs-root /var/tmp/principiis-live-runs --step 2 --retry \
  --authorization private/live/portal-42-recovery-20261117-d5170b18/authorization.md
```

These commands record the actual separate actions. They are not an instruction to
replay completed development. The retained observer script wraps only the final retry
command to measure its starting files; it does not modify developer prompts or code.

The retry completed successfully in 182.847 seconds, preserving checkpoint 2 with
manifest `1ef0af30441f98141122746c288e665db898b8657e1ae7676d15b26b4ccf52ab`.
Its session was `a28f9d1e-f8cc-4048-8e97-f8f53f3528f9`; its model thread was
`01a1eaae-db4b-73a1-afbf-7b76b6519187`. Reported usage was 231,646 input tokens,
212,352 cached-input subset, 7,052 output tokens and 118 reasoning-output subset:
238,698 input plus output. Sampled host Docker-client RSS was 32,210,944 bytes and
container working set was 174,378,188 bytes. The earlier completed checkpoint and
interrupted result/logs/runtime evidence/partial workspace remained unchanged after
the retry; both completed snapshots validated. Exactly one additional retry was used.

## Separate reports, checks and limitations

Each run's saved JSON, CSV and Markdown exports were independently reconciled against
its canonical allocation journal, original results and emitted usage events. Checks
matched run/session/checkpoint/attempt identities, source/log paths, duration, every
exposed token category and unknown fields. Active time was independently summed;
wall time was recomputed from the first start through the last finish. No candidate
JSON file supplied accounting, and the two runs were never pooled.

| Run | Retained attempts | Active development seconds | Wall span seconds, including idle/setup gaps | All-attempt token aggregate |
| --- | ---: | ---: | ---: | --- |
| #40–#41 continuation | 4 | 614.244 | 40627.997 | Unknown: original Docker-start failure has no usage |
| #42 recovery | 3 | 438.237 | 511.044 | Unknown: interrupted turn has no usage |

Known successful-attempt usage remains available individually. Unknown usage is not
zero, and cached/reasoning subsets are not added twice. Spending, API-equivalent
cost and hosted model memory remain unknown. Wall span includes the earlier #40
session and idle gaps; it is not active model time.

Routine regression verification: `python3 -m unittest discover -s tests -v` ran
126 tests in 25.303 seconds: **121 passed, 5 opt-in container tests skipped**. This
included explicit retry eligibility/three-additional-retry limits, SIGTERM retention
and restore, out-of-order/replay/missing-checkpoint rejection, changed-configuration
new-run errors, canonical journal accounting, candidate-owned JSON exclusion and
per-run exports. The skipped opt-in controls were not presented as passing this run;
actual retained Docker/browser/model evidence above supplies the live qualification.
Existing independent implementation review is linked from the [MVP implementation
record](MVP_1_IMPLEMENTATION.md); no production behavior changed during this work.
New evidence reconciliation was performed locally without implementation subagents.

Raw original model command/test failures remain in each attempt's stdout. A developer
session's own unsuccessful intermediate command is not silently erased or converted
into a primary functional/security score. No candidate was repaired by the operator.
The initial inaccurate duplicate-filename smoke label and corrected additional check
are retained explicitly. No hidden oracle, security scoring, data-upgrade assessment
or full pilot was launched.

## Owner acceptance walkthrough and retained artifacts

The automated/live qualification portions of #41 and #42 are complete. At the end of
qualification, owner acceptance remained pending, as required by
[issue #42](https://github.com/SrFlipFlop/principiis-obsta/issues/42). The owner then
accepted the recorded result and instructed: “Great! You can do the PR and merge it.”
This completes milestone-1 owner acceptance and authorizes publishing and merging the
documentation PR for #41 and #42. The original local archive retains its pre-acceptance
status as historical evidence. Hidden evaluation remains unbound.

1. Open **http://127.0.0.1:32769**, register a synthetic account, and inspect the
   actual request-3 portal. The request-2 preview remains at port 32768. Screenshots
   and recorded observations below preserve the exercised collection/member,
   search/archive/restore and selection/export paths.
2. Inspect the continuation report: three completed checkpoints, the original
   Docker-start failure, distinct sessions, source/log locations, metrics and
   `development-complete` next action. Every checkpoint remains `pending_evaluation`.
3. Inspect the recovery report: completed request 1, intentionally interrupted
   request 2, successful explicit retry, distinct sessions and unknown interrupted
   usage. The passive retry-start observation proves exact checkpoint restoration,
   and the qualification audit proves original evidence survived unchanged.
4. Compare each run's JSON/CSV/readable exports with its reconciliation record. The
   recovery status names request 3 as technically eligible; this qualification
   exercise ended after its successful request-2 retry. No further step is scheduled.
5. The owner accepted the real development, preview, continuation, interruption/retry
   and export evidence before milestone-1 closure. Qualified hidden evaluation and
   explicit evaluator binding remain milestone-2 work with their existing prerequisites.

```bash
python3 -m principiis status --run portal-40-20261117-8b873374 \
  --runs-root /var/tmp/principiis-live-runs
python3 -m principiis report --run portal-42-recovery-20261117-d5170b18 \
  --runs-root /var/tmp/principiis-live-runs --format markdown
```

The operating runs remain under `/var/tmp/principiis-live-runs`. The new ignored
archive preserves each run separately and excludes the subscription credential copy;
the earlier #40 archive is unchanged. Archives are evidence copies, not additional
active runs. Each source file's hash is retained in the archive index.

- [Archive index](../../artifacts/live/mvp1-41-42-20261117/summary.json)
- [Continuation readable report](../../artifacts/live/mvp1-41-42-20261117/continuation/run/reports/development.md),
  [JSON](../../artifacts/live/mvp1-41-42-20261117/continuation/run/reports/development.json),
  [CSV](../../artifacts/live/mvp1-41-42-20261117/continuation/run/reports/development.csv)
- [Continuation reconciliation](../../artifacts/live/mvp1-41-42-20261117/continuation/launch/reconciliation.json)
  and [session/boundary/snapshot audit](../../artifacts/live/mvp1-41-42-20261117/continuation/launch/continuation-audit-final.json)
- [Request-2 browser/API observations](../../artifacts/live/mvp1-41-42-20261117/continuation/launch/browser-step2/browser-smoke.json)
  and [collection/member screenshot](../../artifacts/live/mvp1-41-42-20261117/continuation/launch/browser-step2/collection.png)
- [Request-3 browser/API observations](../../artifacts/live/mvp1-41-42-20261117/continuation/launch/browser-step3/browser-smoke.json),
  [search screenshot](../../artifacts/live/mvp1-41-42-20261117/continuation/launch/browser-step3/search.png),
  [archive screenshot](../../artifacts/live/mvp1-41-42-20261117/continuation/launch/browser-step3/archive.png)
  and [actual duplicate-filename/browser ZIP verification](../../artifacts/live/mvp1-41-42-20261117/continuation/launch/browser-export/export-verification.json)
- [Recovery readable report](../../artifacts/live/mvp1-41-42-20261117/recovery/run/reports/development.md),
  [JSON](../../artifacts/live/mvp1-41-42-20261117/recovery/run/reports/development.json),
  [CSV](../../artifacts/live/mvp1-41-42-20261117/recovery/run/reports/development.csv)
- [Planned actual interruption](../../artifacts/live/mvp1-41-42-20261117/recovery/launch/planned-interruption.json),
  [exact retry-start restore](../../artifacts/live/mvp1-41-42-20261117/recovery/launch/retry-start-observation.json),
  [recovery qualification audit](../../artifacts/live/mvp1-41-42-20261117/recovery/launch/qualification-result.json)
  and [reconciliation](../../artifacts/live/mvp1-41-42-20261117/recovery/launch/reconciliation.json)
- [Controller regression log](../../artifacts/live/mvp1-41-42-20261117/recovery/launch/controller-regressions.log)
