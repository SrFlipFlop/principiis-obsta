# Milestone 1 implementation verification — 2026-11-16

Follow-up: [runtime and virtual-environment fixes](MVP_1_RUNTIME_FIXES.md) records
the subsequent resolution of the two implementation blockers below. This document
retains the original failures and verification state.

Scope: implementation foundations for live GitHub issues
[#40](https://github.com/SrFlipFlop/principiis-obsta/issues/40),
[#41](https://github.com/SrFlipFlop/principiis-obsta/issues/41) and
[#42](https://github.com/SrFlipFlop/principiis-obsta/issues/42), read with their comments
and blockers on 2026-11-16. The [approved baseline
specification](../BASELINE_PILOT_SPEC.md) governs this work. All three tickets and
milestone 1 remain open. No live Codex generation, pilot, paid API request, generated
portal acceptance or publication was performed during implementation.

## Delivered behavior

- One operator entry point composes the existing manual controller: reusable
  initialization, explicitly selected development, status, disposable preview and
  saved JSON/CSV/readable reports. Requests 1–3 come from the real content-hashed
  released portal package. Development rehearsal does not need evaluator commands.
- Frozen request/runtime provenance and an explicit unbound evaluator distinguish
  rehearsals from qualified experiments. Evaluation refuses unbound rehearsals.
- A separately prepared container runtime exposes only the current workspace and a
  separately provisioned subscription authentication file, with fresh session/home,
  harness defaults, ordinary tools/network and no development-stage time limit.
- Canonical journals preserve completed and incomplete attempts, enforce explicit
  bounded retries and restore prior completed source without partial edits. Initial
  authorization/provenance survives interruption. Status/report rejects corrupted
  completed evidence and candidate-owned accounting files.
- Preview uses a verified disposable source copy, restricted container, internal
  network and loopback URL. Cleanup covers all previews of a selected checkpoint.
  Reports retain each attempt and preserve unknown token/memory/spending values.

The [operator contract](../../engineering/MVP_DEVELOPMENT_CLI.md) and [runtime
contract](../../engineering/DEVELOPMENT_RUNTIME.md) describe commands, file semantics,
measurement scopes and limitations.

## Verification and failures

Initial repository check: 69 tests ran; 67 passed and two opt-in container tests skipped.
Behavioral red cycles reproduced missing operator commands, absent development-only
support, and missing preview allocation-parent creation before their fixes. New
regressions exercise full operator initialization/development/continuation/retry
through actual local fake-Docker subprocesses, real SIGTERM interruption, retained
usage/logs/workspace evidence and reconciled exports. The preview HTTP response is
substituted in routine tests because the controller sandbox cannot listen on sockets.
These are engineering controls, not generated candidates or oracle qualification.

Independent read-only agent review identified and implementation corrected the
source/output directory conflict, completed-evidence validation in status, unsupported
mount-path preflight and cleanup of earlier previews. Review also identified the
snapshot/environment limitation below and cleanup exit-status preservation; retain
the final verification command/results below.

Follow-up review also corrected active-operation status/serialization and preservation
of known execution status after cleanup failure. A sleeping-process regression
verifies that status says `wait` and a competing retry cannot lose journal history.
Explicit runtime cleanup writes separate evidence while preserving original attempts.

Final routine verification: **108 tests ran in 28.848 seconds: 105 passed, three
opt-in tests skipped**. Compilation and `git diff --check` passed. The new opt-in
preview control was separately exercised on the real daemon as recorded below.
Independent review reported no remaining blocking implementation finding; technical
and live acceptance gates remain open.

Routine command:

```bash
python3 -m unittest discover -s tests -v
git diff --check
```

Local Docker was available only through the permitted unsandboxed tool path; the
ordinary sandbox failed with Snap's `cap_dac_override` check. Read-only inspection
observed daemon 29.8.0 and the existing Python 3.12.12 base image. The first toolchain
build using its bare local image ID failed because BuildKit interpreted it as a
registry repository. The corrected build uses the observed registry reference
`python@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c`.
Build preparation invokes no model or authentication; resulting image/toolchain
qualification must be recorded separately.

The toolchain image built successfully as
`sha256:848b627634e2a1c082949371cc36b41b704af7e7863ccb1c8dff441d0e0f9048`
(`principiis-development:mvp1`). Model-free preflight observed Codex CLI 0.169.0,
Python 3.12.12, Flask 3.1.3 and SQLite 3.46.1. The first nested-sandbox probe used
legacy configuration without the sandbox command's required permission-profile
argument and exited 2; this is a probe invocation failure, not evidence about kernel
sandbox support. Raw tooling/probe evidence is retained at
`artifacts/mvp1-toolchain-qualification-20261116`. The corrected profile probe has
its own evidence below. No authentication file was mounted in these checks.

The corrected `codex sandbox --permission-profile :workspace` control exited 1:
`bwrap: No permissions to create a new namespace`. Evidence is retained at
`artifacts/mvp1-toolchain-qualification-20261116-profile`. A separate diagnostic
using the repository's existing evaluation seccomp profile also exited 1, reaching
`bwrap: Failed to make / slave: Operation not permitted`. Its evidence is at
`artifacts/mvp1-toolchain-qualification-20261116-seccomp`. This distinguishes the
observed syscall-policy failures from the first CLI argument error; it does not
prove which remaining host/profile setting is sufficient. Runtime qualification is
**blocked** until a reviewed namespace/mount policy supports the normal nested
workspace sandbox. No extra capabilities, unconfined profile, sandbox bypass or
permission change was added to the development adapter to mask these failures.

The first actual model-free HTTP preview control failed because this Docker host
provided no published port for an internal-only application container. Evidence is
retained at `artifacts/mvp1-runtime-qualification-20261116`; cleanup succeeded. The
corrected design uses an isolated application network and a trusted fixed-target TCP
relay that alone publishes loopback. Read-only review checked this isolation shape.
The opt-in control then **passed in 23.837 seconds**, retaining evidence at
`artifacts/mvp1-preview-controls/http-control-23b0efd9e5444cb099f7b5d2c81c6aae`.
It checked effective container/network restrictions, source integrity, HTTP readiness,
binary POST forwarding, cookie headers and removal of both containers/network.
This establishes an engineering HTTP path, not browser or generated-portal acceptance.
After review added Python `-S` to the isolated relay, the final version **passed in
23.197 seconds**, retaining a separate control at
`artifacts/mvp1-preview-controls/http-control-15b0714fe273427096d71d5f9276f3f8`.
All resources were removed in both controls.
The control is reproducible without model calls:

```bash
PO_PREVIEW_IMAGE=sha256:5265ced2e36c835ba9c04ed8be4eea1ec30d9523da97c7797bbc6d9a4b3fcfcb \
PO_PREVIEW_ROOT="$PWD/artifacts/mvp1-preview-controls" \
python3 -m unittest discover -s tests -p test_preview_containers.py -v
```

## Acceptance still required

1. Resolve the observed nested workspace sandbox failure, complete model-free
   qualification and review the prepared image/access boundary. Neither a review
   string nor fixture tests prove that arbitrary image contents are clean.
2. Resolve/qualify source-versus-environment file semantics. A conventional
   `.venv/bin/python` absolute symlink currently fails the self-contained snapshot
   contract, retaining an incomplete attempt. No benchmark instruction steers the
   agent away from ordinary dependencies or environments.
3. Qualify restricted candidate dependency preparation and actual preview/browser
   behavior. Flask is prepared, but additional dependencies remain the agent's choice.
4. Obtain and record scoped live authorization only once the runtime is reviewable.
   Then retain real portal requests 1–3, actual preview observations and a separately
   identified interruption/recovery run. Preserve failures; do not repair candidates
   outside development or replay completed generation for a favorable outcome.
5. Reconcile those real runs and perform owner milestone acceptance. Fixture success
   does not close any live acceptance criterion or authorize the full pilot.
