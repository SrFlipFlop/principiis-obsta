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
