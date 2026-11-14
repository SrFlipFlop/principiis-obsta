> Archived preliminary synthetic package. The canonical real application benchmark is [document-portal-real](../document-portal-real/BENCHMARK_DESIGN.md). This archive is released only with explicit `--edition original`; its qualification does not apply to real-v1.

# Document portal author package, version 1

Three requests cover initial build and two changes. This is benchmark authoring only; no evaluated coding agent has generated an application. The package remains **pending owner review** and is not the approved suite authoring example yet. The initial development workspace must be empty.

Selected build stack: Python 3.12, Flask 3.1, SQLite, server-rendered HTML enhanced with ordinary JavaScript. Minimal startup, API and accessible browser contracts are in the requests. Layout, database schema, Flask structure and internal architecture remain open. Requests are original project-authored material under the repository license, not adapted third-party benchmark tasks. No production identity provider or external integration is involved.

Release only current/past requirements:

```sh
python3 -m principiis.portal release --edition original --step 1 --output /tmp/new-portal-release
```

The new directory contains only `request.txt`. Supply its contents to a fresh empty development workspace. Later releases concatenate only requests through the selected step. The public research checkout contains future requests and must never be accessible to evaluated sessions; the ordinary Codex adapter's separate reviewed runtime boundary still applies.

The hidden bundle is local, separately versioned, and ignored under `private/benchmarks/document-portal-checker-2/` (the original version remains unchanged under `private/benchmarks/document-portal/`) in the main research checkout. It contains executable checks, controls, image recipes, the property rubric, qualification evidence references and the concrete owner review document. None belongs in developer contexts or a public PR. Its immutable metadata digest is recorded in `package.json`; it must be supplied explicitly:

```sh
python3 -m principiis.portal bind --edition original --bundle /local/private/bundle --output /tmp/new-author-manifest
```

This creates a sequence manifest consumable by `python3 -m principiis sequence --sequence /tmp/new-author-manifest/sequence.json ...`. The author manifest and its private check argv remain controller-side. Do not copy this directory into development. `bind` neither starts development nor authorizes a model run.

For model-free assessment of an existing checkpoint:

```sh
python3 -m principiis.portal evaluate --edition original --bundle /local/private/bundle --step 1 --snapshot /local/checkpoint
```

The adapter verifies bundle file hashes, stages candidate source under private Docker-visible storage, and delegates to the #6 restricted browser/backend runner. Only score JSON goes to the caller; detailed results remain in a fresh private evidence directory. Candidate code is never executed on the host. Prepared pinned images and the unchanged containment profile are required; dependency preparation occurs before restricted runtime. Assessment failures remain unassessable. The generic evaluator's optional `--check-contract` accepts an author-only JSON mapping of required check IDs to `functional` or `security`; it requires both classes, exact coverage and valid check statuses, retaining the check-map digest. Without this flag the #6 engineering fixture contract is unchanged.

The original checker completed 18 local browser/backend assessments covering safe, property-violating, reject-all, alternative-valid and repeated controls at each checkpoint. Checker revision 2 corrects overly restrictive browser assertions while retaining the version-1 task contract and pending rubric. Its new qualification is **pending**: ordinary Docker fails under the current environment permissions, so none of the original assessments is claimed as evidence for the revision. The revised bundle omits unprepared image pins, and `evaluate` refuses pending qualification before staging or running a candidate. New source/image hashes and restricted browser/backend regression evidence are required before enabling assessment. The private controls are independently authored oracle fixtures, not Flask application skeletons or material for evaluated development. Alternative storage access paths retain the same observable contract. Qualification is limited to declared executable properties and is not a model run, reliability estimate or comprehensive security audit. Owner review must resolve the private rubric and mappings before this package can close issue #8 or seed the rest of the suite.

Author-only custom qualification fixtures may use the restricted evaluator's `--fixture-variant` with `--check-contract`; names must be lowercase alphanumeric/hyphen identifiers. This cannot be combined with a nondefault `--control`. The existing engineering fixture controls retain their original choices and defaults. Variant names are fixture arguments inside the same restricted container boundary.
