# Core independent review corrections

Checked 2026-11-14. Engineering fixture evidence only; no model runs or pilot results.

Standards finding (P2): evaluator stdout/stderr now open as retained files before
launch. The measured subprocess seam flushes each emitted line directly to disk.
A real sleeping evaluator emits both streams, then the test SIGKILLs its controller;
logs survive and scores remain unknown with completed=false. Hard controller death
can still leave a child process running; the regression explicitly cleans it up.

Spec findings (P1): checkpoints preserve internal relative symlinks, including
ordinary package-manager style links, but reject absolute or escaping links and
special files without reading their targets. A rejected checkpoint remains
incomplete with snapshot_error, the successful executor evidence, workspace and
unknown scores. This deliberately rejects even absolute links back into the
workspace: users must produce relocatable output. A sibling snapshot.json records
file hashes, modes, directories and link targets. Controller evaluation, restore,
and resume verify it; restricted standalone evaluation verifies it when supplied.
Standalone fixture directories without manifests remain supported, and its existing
container bind-mount evaluator still rejects symlinks. Manifests detect accidental
corruption, not a malicious researcher who can rewrite artifacts and manifests.

Regression evidence demonstrates evaluation mutation and later workspace mutation
cannot change a snapshot through an internal link; retained snapshot mutation blocks
resume and rescore before candidate execution. Existing failure and retry records
remain append-only. Interrupted development artifacts with empty execution metadata
now count in inspection and retain available turn.completed usage. Missing elapsed
time and local memory remain unknown, and unknown durations propagate into totals.
Existing duplicate-session checks still prevent duplicate usage accounting.

Optional review suggestions implemented narrowly: task-relative evaluator argv
resolution lives in task.py; process supervision and sampling live in execution.py.
resource.execute remains a compatibility import for the agreed subprocess seam.
No plugin framework or dependency added.

Validation: python3 -m unittest discover -s tests. Five new CLI/artifact regressions
failed against the original behavior and pass with the fixes. The suite includes a
Docker-dependent qualification test that remains explicitly skipped unless enabled.
