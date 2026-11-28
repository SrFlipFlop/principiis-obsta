# Explicit portal evaluation commands (#43–#45)

These commands compose the retained checkpoint controller. They implement operator
boundaries; engineering controls do not complete live acceptance. The current portal
release is qualified through request 3 only; #9 remains the
ten-step prerequisite. Existing milestone-1 snapshots
retain their development results. No primary assessment is inferred
from a preview, candidate-owned test, source inspection or a historical control score.

Bind a qualified evaluator release when creating the run:

```bash
python3 -m principiis init --run portal-first --runs-root /operator/runs \
  --application document-portal --steps 3 \
  --runtime-config /operator/config/development-runtime.json \
  --evaluator-manifest /operator/private/portal/release-manifest.json
```

Initialization writes a separate `evaluator-binding.json`; it never rewrites
`configuration.json`, the development journal, snapshots or development results.
The public package must pin the complete private declaration, with matching released
request versions/hashes, qualified checks, resolved runtime/image identities and a
complete dependency inventory with preparation evidence. A changed declaration
requires a new identified run; preserve
earlier evidence. An unqualified, unbound or incompatible bundle fails before an
assessment or model launch. A declaration is not evidence that a package passed
qualification; benchmark authors must supply and retain that actual evidence.
Older unbound runs remain readable but cannot gain an evaluator through the simplified
operator CLI; create a new run with the manifest at initialization.

**Evaluator files are found by SHA-256, not path (#75 item 3).**

`bind` (and so `init --evaluator-manifest` and `derive-evaluation`) copies the manifest
and every hashed dependency file into the run at `evaluator/`, then records
`manifest: "evaluator/<name>"` (relative to the run) plus `source_manifest` (the original
absolute path, audit only, never used for identity). `evaluate` reads the run's own copy
and re-verifies every hash, so a new run is self-contained: moving or deleting the
original evaluator changes nothing, and editing the original is irrelevant. Tampering
with the copy fails with `evaluator dependency content changed`.

Runs bound before this change record an absolute `manifest` path and have no copy.
Their records are never rewritten. `evaluate` finds the evaluator by SHA-256
(`manifest_sha256` and every `files` hash must all match) in this order: the recorded
path, the repository's `benchmarks/*/evaluator/*/` tree, then any configured root:
`principiis evaluate --evaluator-root DIR` (repeatable) or the
`PRINCIPIIS_EVALUATOR_ROOT` environment variable (path-separator list). Under a configured root
the directory itself and every directory containing a file with the manifest's name are
tried. Same-named files with other content are skipped; a hash mismatch is never
accepted, and if nothing matches the command fails before allocating an assessment.
Lookup is per directory: the manifest and all its dependencies must match in one place.
Limitation: the published `benchmarks/` evaluator is a sanitised package whose manifest
may hash differently from a private manifest an old run recorded; such a run needs the
original bytes under a configured root.

The package rule that the manifest's `owner_review` must equal the package's value is
unchanged (`pending_owner_review` packages cannot bind), as are all other integrity checks.

For a retained completed development run whose evaluator binding must remain frozen,
`derive-evaluation` creates a **new evaluation-only run** with an independently
qualified evaluator binding. It copies and attests the source run's
development journal, results, logs and snapshots, but imports no old primary scores.
The source run is not changed and the derived run rejects `develop`:

```bash
python3 -m principiis derive-evaluation --runs-root /operator/runs \
  --source-run original-run --run corrected-evaluation \
  --evaluator-manifest /operator/private/portal/corrected-release.json
python3 -m principiis evaluate --runs-root /operator/runs \
  --run corrected-evaluation --step 1
```

All source checkpoints must have completed development, and development, evaluation
and reviewer runtime cleanup must be resolved. The current package version must
match the source's frozen package version; unchanged request bytes do not justify
relabelling a development run with a newer package identity. The command validates
the original journal and snapshots, records
the source run, source configuration/binding hashes and copied-file hashes in
`lineage.json`, then binds the new evaluator before exposing the run. `status` checks
that imported development evidence and the source binding state remain byte-identical.
Existing `evaluate`,
`--rerun` and report commands use the derived run's separate canonical assessment
ledger. Reports mark imported development measurements as copied evidence; they are
not additional model usage. Comparing source and derived reports must not sum their
development tokens as independent sessions. A new release still needs its own control tests
([ADR 0002](../adr/0002-control-tests-qualify-evaluator-versions.md)); this import does not qualify it.
A run binds only when its frozen steps are a prefix of the package requests no longer
than the package's `qualified_through`, and the private manifest matches every frozen
request. A full-sequence run additionally needs its evaluator manifest at `init`.

Dependency preparation remains an explicit prerequisite: the operator command does
not guess dependencies, create a lockfile or adapt an incompatible historical bundle.
Prepared application/checker images and their complete inventories and receipts must
cover the actual retained candidate. Application files execute only through the
restricted evaluator in a disposable copy; evaluation never launches development or
repairs the candidate. Keep hidden tests and results outside
development contexts and public Git.

The declaration includes `version`, `complete`, an optional `evaluator_command` argv
(default `["node", "/oracle/check.cjs"]`), `requests` (released path/hash pairs), `files` (private dependency path/hash pairs),
`runtime_image`, `evaluator_images` keyed by frozen checkpoint ID, and `steps` mapping
each checkpoint to its `contract` and `app_command`. `seccomp` and
`dependency_manifest` name hashed dependencies. The dependency inventory maps exact
image IDs to resolved package names/versions and hashed preparation receipts.
Binding retains frozen public/private metadata copies so historical reports remain
readable after a subsequent author release. `init` and `derive-evaluation` verify the
whole declaration once, when binding. Before allocating an assessment, `evaluate`
re-hashes only the private files that step uses (its check contract and the seccomp
profile) against the binding and refuses on any change; the restricted evaluator
image IDs stay pinned by the binding.

For each assessment, the controller inventories installed distribution metadata in
retained Python virtual environments before launching the restricted runtime. The
assessment retains each environment's configuration hash and each distribution's
name, version, metadata path and hash, tied to the immutable snapshot manifest. The
snapshot manifest pins the complete file tree, including package payloads. Unsupported
legacy `.egg-info` / `.egg-link` metadata or malformed `.dist-info/METADATA` stops the
launch as an evaluator error. The bound author inventory continues to cover prepared
runtime/checker images. The controller does not install candidate dependencies or
infer them from a requirements file; an incompatible or missing runtime dependency
remains an evaluator error. A candidate using dependencies outside the image and
retained virtual environments needs separate preparation and qualification before
assessment. Live generated-candidate acceptance was completed under #43 and #44.
The current retained Document Portal snapshots have no virtual environment; the
first-three release inventories their pinned runtime and checker images and records
their requirements-file hashes. A different candidate environment needs its own
preparation and inventory.
Only the disposable application copy has its owner permission bits mirrored to the
fixed runtime user's access bits, preserving executable and read-only intent on this
host. Retained modes and bytes are unchanged. Permission-sensitive checks require
qualification of this explicit runtime policy.

The operator explicitly evaluates one completed checkpoint by running the command:

```bash
python3 -m principiis evaluate --run portal-first --runs-root /operator/runs \
  --step 1
python3 -m principiis evaluate --run portal-first --runs-root /operator/runs \
  --step 2
python3 -m principiis evaluate --run portal-first --runs-root /operator/runs \
  --step 3
```

Each invocation assesses only the selected retained snapshot. The command itself is
the operator action; its attempt, outcome and timing are retained. The
per-run operation lock serializes evaluation, development and preview changes.
Status remains available and marks an active operation with partial measurements.

An assessment rerun is a separate explicit action:

```bash
python3 -m principiis evaluate --run portal-first --runs-root /operator/runs \
  --step 3 --rerun
```

The first assessment remains primary, including a candidate failure, unassessable
outcome or evaluator error. Reruns append provenance, logs and measurements and do
not change the primary result, snapshot or development result. A candidate failing
evaluation does not become eligible for a development retry. Only incomplete
development attempts retain the existing explicit retry path.

SIGINT/SIGTERM retain an interrupted assessment and allow up to 75 seconds for bounded
runner teardown; this is cleanup grace, not a development/model timeout. Runtime
container identities and cleanup commands are saved before launch. If cleanup fails
or is interrupted, status names `cleanup-evaluation` and further development and
evaluation are blocked. Explicitly remove the recorded containers:

```bash
python3 -m principiis cleanup-evaluation --run portal-first --runs-root /operator/runs --step 3
```

Cleanup saves separately timed receipts under `evaluation-cleanups/`. Successful
receipts reconcile the retained runtime allocation without changing primary/rerun
results. Failed receipts remain evidence and keep the block. Unknown container
identities require inspection of retained runtime evidence. Cleanup receipts are
separate operational measurements, outside development/evaluation stage totals.

```bash
python3 -m principiis status --run portal-first --runs-root /operator/runs --format json
python3 -m principiis report --run portal-first --runs-root /operator/runs --format csv
```

The existing `reports/development.json`, `.csv` and `.md` files now join canonical
development allocations with all primary/rerun assessments. JSON exposes each
checkpoint's `primary_assessment` and assessment history. CSV has separate development
and evaluation rows, with stage, role, evaluator version, snapshot identity, source/log
paths, outcomes and stage measurements. Totals sum each selected allocation once.
Unknown tokens, spending and hosted model memory stay unknown; deterministic checks
do not invent model usage. Functional/security passes require actual check evidence.
Missing checks, unavailable runtimes and evaluator errors remain explicit outcomes.
Saved reports are derived exports and can be regenerated without changing source
evidence. All three formats remain operator artifacts containing hidden results.

For a full-sequence qualification run, use `init --steps 10` once the package's
`qualified_through` reaches 10 (for the portal this needs #9). It freezes every request
contract before allocation; shorter runs within `qualified_through` remain available. Bind the qualified evaluator before
the first development session. Each further development step requires a separately
retained primary assessment of the previous completed checkpoint. Candidate failure,
unassessable results and evaluator errors remain part of the record and permit the
next explicit development step. No command starts the next development/evaluation
stage automatically. An existing three-step run cannot be extended or rebound in
place; changed frozen contracts require a new run from an empty project.

Where upgrade/data-survival behavior is required, #8/#9 must supply a qualified,
versioned executable continuation fixture. Preserving source is not migration
evidence. Owner milestone acceptance, actual generated browser/backend evidence and
resource reconciliation remain separate requirements; these commands do not declare
milestone 2 complete or establish model reliability or intervention efficacy.
