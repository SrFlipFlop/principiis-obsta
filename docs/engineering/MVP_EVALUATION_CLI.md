# Explicit portal evaluation commands (#43–#45)

These commands compose the retained checkpoint controller. They implement operator
boundaries; engineering controls do not complete live acceptance. The current portal
release is unqualified: #8 and #9 remain prerequisites. Existing milestone-1 snapshots
retain their development results and fingerprints. No primary assessment is inferred
from a preview, candidate-owned test, source inspection or a historical control score.

Bind a qualified, owner-approved evaluator release to a compatible frozen run:

```bash
python3 -m principiis bind-evaluator --run portal-first --runs-root /operator/runs \
  --evaluator-manifest /operator/private/portal/bundle.json
```

Binding writes a separate `evaluator-binding.json`; it never rewrites
`configuration.json`, the development journal, snapshots or development results.
The public package must pin the complete private declaration, with matching released
request versions/hashes, qualified checks, resolved runtime/image identities and a
complete dependency inventory with preparation evidence. Repeating an identical
binding is idempotent. A changed declaration requires a new identified run; preserve
earlier evidence. An unqualified, unbound or incompatible bundle fails before an
assessment or model launch. A declaration is not evidence that a package passed
qualification; benchmark authors must supply and retain that actual evidence.

Dependency preparation remains an explicit prerequisite: the operator command does
not guess dependencies, create a lockfile or adapt an incompatible historical bundle.
Prepared application/checker images and their complete inventories and receipts must
cover the actual retained candidate. Application files execute only through the
restricted evaluator in a disposable copy; evaluation never launches development or
repairs the candidate. Keep hidden tests, results and all authorization records outside
development contexts and public Git.

The declaration includes `version`, `complete`, `qualification_status`, `owner_review`,
`requests` (released path/hash pairs), `files` (private dependency path/hash pairs),
`runtime_image`, `evaluator_images` keyed by frozen checkpoint ID, and `steps` mapping
each checkpoint to its `contract` and `app_command`. `seccomp` and
`dependency_manifest` name hashed dependencies. The dependency inventory maps exact
image IDs to resolved package names/versions and hashed preparation receipts.
Binding retains frozen public/private metadata copies so historical reports remain
readable after a subsequent author release; evaluation verifies the original private
dependencies again before allocation.

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
assessment. Live generated-candidate acceptance remains required for #43.
The current retained Document Portal snapshots have no virtual environment; the
first-three release inventories their pinned runtime and checker images and records
their requirements-file hashes. A different candidate environment needs its own
preparation and inventory.
Only the disposable application copy has its owner permission bits mirrored to the
fixed runtime user's access bits, preserving executable and read-only intent on this
host. Retained modes and bytes are unchanged. Permission-sensitive checks require
qualification of this explicit runtime policy.

After recording owner authorization for this specific live scope in a private UTF-8
file, explicitly evaluate one completed checkpoint:

```bash
python3 -m principiis evaluate --run portal-first --runs-root /operator/runs \
  --step 1 --authorization /operator/private/evaluation-approval.md
python3 -m principiis evaluate --run portal-first --runs-root /operator/runs \
  --step 2 --authorization /operator/private/evaluation-approval.md
python3 -m principiis evaluate --run portal-first --runs-root /operator/runs \
  --step 3 --authorization /operator/private/evaluation-approval.md
```

Each invocation assesses only the selected retained snapshot. The command saves the
authorization record as audit evidence; it cannot independently decide whether the
owner approved its scope. A nonempty file alone does not grant authorization. The
per-run operation lock serializes binding, evaluation, development and preview changes.
Status remains available and marks an active operation with partial measurements.

An assessment rerun is a separate explicit action:

```bash
python3 -m principiis evaluate --run portal-first --runs-root /operator/runs \
  --step 3 --rerun --authorization /operator/private/evaluation-approval.md
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

For a new ten-step qualification run, use `init --steps 10`. This requires #9's
qualified package and freezes all ten request contracts before allocation; the
default three-step rehearsal remains available. Bind the qualified evaluator before
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

The restricted runner now supports an optional versioned predecessor-data overlay.
For a step that requires it, the qualified private declaration sets
`steps.<checkpoint>.continuation` to `{"version":"...", "from_checkpoint":"step-01", "paths":["relative/data.db"]}`.
Binding rejects a future or missing predecessor, duplicate paths and traversal.
The operator selects the completed predecessor snapshot from the frozen run; it
cannot be supplied at evaluation time. The runner validates its retained manifest,
copies only named regular files into the disposable current application tree before
launch, and records the predecessor snapshot digest, manifest hash, database hashes,
contract version and unchanged-input checks. The current snapshot and predecessor
snapshot remain untouched. The hidden checker must exercise known prior records in
the new application through its browser/backend contract; a successful file copy is
preparation evidence, not a passing migration check. Include associated database
journal files in `paths` when the application requires them. A new continuation
declaration changes the private bundle hash and therefore requires qualification and
a new bound run; existing runs cannot be silently rebound.
