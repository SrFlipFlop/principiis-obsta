# Explicit portal evaluation commands (#43–#45)

These commands compose the retained checkpoint controller. They implement operator
boundaries; engineering controls do not complete live acceptance. The current portal
release is qualified and owner-approved through request 3 only; #9 remains the
ten-step prerequisite. Existing milestone-1 snapshots
retain their development results and fingerprints. No primary assessment is inferred
from a preview, candidate-owned test, source inspection or a historical control score.

Bind a qualified, owner-approved evaluator release when creating the run:

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
For a three-step run, the public `qualified_first_three` / `approved_first_three`
declaration and private manifest must match all three frozen requests. The ten-step
initialization gate still requires a separately qualified full package from #9 and its evaluator manifest.

Dependency preparation remains an explicit prerequisite: the operator command does
not guess dependencies, create a lockfile or adapt an incompatible historical bundle.
Prepared application/checker images and their complete inventories and receipts must
cover the actual retained candidate. Application files execute only through the
restricted evaluator in a disposable copy; evaluation never launches development or
repairs the candidate. Keep hidden tests and results outside
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

Candidate-specific dependency installation and a complete inventory of packages
inside retained virtual environments are not implemented here. Author image
inventories alone do not establish that completeness. The runtime must match the
development image for image-bound interpreter links; missing dependencies stay
evaluator errors. This remains an incomplete part of #43, alongside live acceptance.
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
