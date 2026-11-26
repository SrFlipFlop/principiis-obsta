# Issue #40 — authorized real development run, 2026-11-17

The owner instructed: “Great! Start the run for #40.” The recorded scope was portal
request 1, existing subscription, harness-default model/reasoning, retained evidence
and restricted preview. No subsequent request, hidden evaluation, paid API or public
publication ran. Implementation subagents were not used for this launch; the evaluated
Codex process was the subject of the run.

Run `portal-40-20261117-8b873374` completed request 1 of package `v3-draft1`, exited
zero and preserved its original generated source. The resulting Flask application
started in a disposable restricted preview. A sandboxed Chromium browser loaded the
login page and populated personal library; thirteen positive API smoke observations
passed. These observations use the visible request contract and are not qualified
primary functional/security scores. The evaluator remains unbound.

## Commands and provenance

The initial run was initialized outside the research checkout with the prepared image
and a separately copied subscription authentication file. Before launch, an operational
review checked the adapter, image recipe, retained qualification controls and actual
empty-image access. The actual running development container inspection confirmed
only the workspace and read-only authentication bind, nonroot UID, dropped capabilities
and read-only outer root. Authentication bytes were never printed or archived.

```bash
python3 -m principiis init --application document-portal \
  --run portal-40-20261117-8b873374 --runs-root /tmp/principiis-live-runs \
  --runtime-config private/live/portal-40-20261117-8b873374/runtime.json
python3 -m principiis develop --run portal-40-20261117-8b873374 \
  --runs-root /tmp/principiis-live-runs --step 1 \
  --authorization private/live/portal-40-20261117-8b873374/authorization.md
```

That first controller attempt failed at Docker startup with exit 125: this host's
Snap Docker daemon could not see the controller's `/tmp` bind source. Codex never
started; the workspace and model event log stayed empty. The complete original
attempt was preserved. A harmless bind control verified `/var/tmp` visibility; the
complete run journal was copied there and continued with one explicit controller
retry to perform the still-requested first model invocation. Both attempts remain
in the same journal; there was one model invocation and no candidate regeneration.

```bash
python3 -m principiis develop --run portal-40-20261117-8b873374 \
  --runs-root /var/tmp/principiis-live-runs --step 1 --retry \
  --authorization private/live/portal-40-20261117-8b873374/authorization-infrastructure-recovery.md
python3 -m principiis preview --run portal-40-20261117-8b873374 \
  --runs-root /var/tmp/principiis-live-runs --step 1 \
  --preview-config private/live/portal-40-20261117-8b873374/preview-config.json
python3 -m principiis report --run portal-40-20261117-8b873374 \
  --runs-root /var/tmp/principiis-live-runs --format markdown
```

Harness: Codex CLI 0.169.0; requested model/reasoning: default, effective values not
exposed and recorded unknown. Image:
`sha256:848b627634e2a1c082949371cc36b41b704af7e7863ccb1c8dff441d0e0f9048`.
The controller was uncommitted implementation work based on Git HEAD
`8bcbd2316f3ce1e91665265ebfe62aca4b63cdc5`; the archive retains its exact source files
and launch hash manifest. The actual model thread, controller run/session identities,
request hashes, permissions, policy hash, commands, logs and cleanup evidence are
retained without rewriting the original results.

## Observed application and measurements

The candidate supplied `app.py`, templates/static assets, `requirements.txt`, its own
tests and startup documentation. Dependencies were compatible with the prepared Flask
image; no candidate source repair or additional model session was needed. Preview
uses a separate writable copy; the retained snapshot was verified unchanged after
browser/API activity. Its manifest SHA-256 is
`15fd0d690c6d71c2716cd6dec80d066127211ca95e1562640454197ad6b7e62a`.

| Successful development attempt measurement | Observed value |
| --- | --- |
| Monotonic elapsed stage time | 221.111 seconds |
| Reported input tokens | 103,495 |
| Cached input subset | 85,888 |
| Reported output tokens | 9,309 |
| Reasoning output subset | 46 |
| Input plus output | 112,804 |
| Sampled container working set | 179,201,638 bytes |
| Sampled host Docker client process-group RSS | 32,944,128 bytes |
| Actual subscription spending / hosted model RAM | Unknown / unobservable |

The failed Docker launch retains its 0.159-second measured duration and unknown token
usage. The all-attempt aggregate correctly remains unknown for tokens when one attempt
has no reported usage; the successful attempt's known usage is separately available.
Do not double-count cached or reasoning subsets. Docker working-set samples are
rounded and are neither RSS nor a guaranteed peak. Stage elapsed time uses a monotonic
clock; wall timestamps and idle/setup gaps are separate.

The positive smoke used synthetic accounts and data in the disposable preview copy.
It observed backend readiness, registration, cookie login/current session, note
creation/edit/download, binary file upload/exact download, listing, deletion and logout.
Chromium screenshots show the actual generated login and library pages. No hidden
checks, security scoring or later-step requirements were supplied to development.

## Artifacts and operating preview

The live preview is **http://127.0.0.1:32768**. It remains running for owner inspection;
development and browser-check containers were removed. Register a new test account
through the portal to try its UI.

- [Retained summary](../../../artifacts/live/portal-40-20261117-8b873374/summary.json)
- [Generated source](../../../artifacts/live/portal-40-20261117-8b873374/run/development/attempts/step-01/2/snapshot/app.py)
- [Generated startup documentation](../../../artifacts/live/portal-40-20261117-8b873374/run/development/attempts/step-01/2/snapshot/README.md)
- [Development report](../../../artifacts/live/portal-40-20261117-8b873374/run/reports/development.md)
- [JSON](../../../artifacts/live/portal-40-20261117-8b873374/run/reports/development.json) and
  [CSV](../../../artifacts/live/portal-40-20261117-8b873374/run/reports/development.csv) exports
- [Browser/API observations](../../../artifacts/live/portal-40-20261117-8b873374/launch/browser/browser-smoke.json)
- [Library screenshot](../../../artifacts/live/portal-40-20261117-8b873374/launch/browser/library.png) and
  [login screenshot](../../../artifacts/live/portal-40-20261117-8b873374/launch/browser/landing.png)

Raw artifacts are ignored local evidence, not published repository assets. The archive
excludes subscription authentication. Current operable controller artifacts remain at
`/var/tmp/principiis-live-runs/portal-40-20261117-8b873374`; the archive is a preserved
copy and is not a second active run. Stop the preview with:

```bash
python3 -m principiis preview --run portal-40-20261117-8b873374 \
  --runs-root /var/tmp/principiis-live-runs --step 1 --stop
```

At launch completion, issue #40 remained open for owner acceptance; no issue comment,
closure or next-step run was performed by the launch. The owner subsequently accepted
the result and authorized merging the implementation in this conversation. The linked
implementation PR records #40 acceptance; current issue status lives in GitHub.
